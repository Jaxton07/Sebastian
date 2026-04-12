package com.sebastian.android.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sebastian.android.data.model.ContentBlock
import com.sebastian.android.data.model.Message
import com.sebastian.android.data.model.MessageRole
import com.sebastian.android.data.model.StreamEvent
import com.sebastian.android.data.model.ToolStatus
import com.sebastian.android.data.repository.ChatRepository
import com.sebastian.android.data.repository.SettingsRepository
import com.sebastian.android.di.IoDispatcher
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject

enum class ComposerState { IDLE_EMPTY, IDLE_READY, SENDING, STREAMING, CANCELLING }
enum class ScrollFollowState { FOLLOWING, DETACHED, NEAR_BOTTOM }
enum class AgentAnimState { IDLE, THINKING, STREAMING, WORKING }

data class PendingApproval(
    val approvalId: String,
    val sessionId: String,
    val description: String,
)

data class ChatUiState(
    val messages: List<Message> = emptyList(),
    val composerState: ComposerState = ComposerState.IDLE_EMPTY,
    val scrollFollowState: ScrollFollowState = ScrollFollowState.FOLLOWING,
    val agentAnimState: AgentAnimState = AgentAnimState.IDLE,
    val activeThinkingEffort: String? = null,
    val isOffline: Boolean = false,
    val pendingApprovals: List<PendingApproval> = emptyList(),
    val error: String? = null,
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val chatRepository: ChatRepository,
    private val settingsRepository: SettingsRepository,
    @IoDispatcher private val dispatcher: CoroutineDispatcher,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    private var currentAssistantMessageId: String? = null
    private var pendingTurnSessionId: String? = null
    private val sseScope = CoroutineScope(dispatcher + SupervisorJob())

    init {
        startSseCollection()
    }

    override fun onCleared() {
        super.onCleared()
        sseScope.cancel()
    }

    private fun startSseCollection() {
        sseScope.launch {
            val baseUrl = settingsRepository.serverUrl.first()
            chatRepository.sessionStream(baseUrl, "main", "").collect { event ->
                handleEvent(event)
            }
        }
    }

    private fun handleEvent(event: StreamEvent) {
        when (event) {
            is StreamEvent.TurnReceived -> {
                // Defer message creation until the first block arrives to avoid
                // emitting an intermediate IDLE_EMPTY state with an empty message.
                pendingTurnSessionId = event.sessionId
                currentAssistantMessageId = UUID.randomUUID().toString()
            }

            is StreamEvent.ThinkingBlockStart -> {
                val block = ContentBlock.ThinkingBlock(blockId = event.blockId, text = "")
                appendBlockToCurrentMessage(block, agentAnimState = AgentAnimState.THINKING)
            }

            is StreamEvent.ThinkingDelta -> {
                updateBlockInCurrentMessage(event.blockId) { existing ->
                    if (existing is ContentBlock.ThinkingBlock) {
                        existing.copy(text = existing.text + event.delta)
                    } else existing
                }
            }

            is StreamEvent.ThinkingBlockStop -> {
                updateBlockInCurrentMessage(event.blockId) { existing ->
                    if (existing is ContentBlock.ThinkingBlock) existing.copy(done = true)
                    else existing
                }
            }

            is StreamEvent.TextBlockStart -> {
                val block = ContentBlock.TextBlock(blockId = event.blockId, text = "")
                appendBlockToCurrentMessage(
                    block,
                    composerState = ComposerState.STREAMING,
                    agentAnimState = AgentAnimState.STREAMING,
                )
            }

            is StreamEvent.TextDelta -> {
                updateBlockInCurrentMessage(event.blockId) { existing ->
                    if (existing is ContentBlock.TextBlock) {
                        existing.copy(text = existing.text + event.delta)
                    } else existing
                }
            }

            is StreamEvent.TextBlockStop -> {
                updateBlockInCurrentMessage(event.blockId) { existing ->
                    if (existing is ContentBlock.TextBlock) existing.copy(done = true)
                    else existing
                }
            }

            is StreamEvent.ToolBlockStart -> {
                val block = ContentBlock.ToolBlock(
                    blockId = event.blockId,
                    toolId = event.toolId,
                    name = event.name,
                    inputs = "",
                    status = ToolStatus.PENDING,
                )
                appendBlockToCurrentMessage(block, agentAnimState = AgentAnimState.WORKING)
            }

            is StreamEvent.ToolBlockStop -> {
                updateBlockInCurrentMessage(event.blockId) { existing ->
                    if (existing is ContentBlock.ToolBlock) {
                        existing.copy(inputs = event.inputs, status = ToolStatus.RUNNING)
                    } else existing
                }
            }

            is StreamEvent.ToolRunning -> {
                updateToolBlockByToolId(event.toolId) { existing ->
                    existing.copy(status = ToolStatus.RUNNING)
                }
            }

            is StreamEvent.ToolExecuted -> {
                updateToolBlockByToolId(event.toolId) { existing ->
                    existing.copy(status = ToolStatus.DONE, resultSummary = event.resultSummary)
                }
            }

            is StreamEvent.ToolFailed -> {
                updateToolBlockByToolId(event.toolId) { existing ->
                    existing.copy(status = ToolStatus.FAILED, error = event.error)
                }
            }

            is StreamEvent.TurnResponse -> {
                currentAssistantMessageId = null
                pendingTurnSessionId = null
                _uiState.update {
                    it.copy(
                        composerState = ComposerState.IDLE_EMPTY,
                        agentAnimState = AgentAnimState.IDLE,
                    )
                }
            }

            is StreamEvent.TurnInterrupted -> {
                currentAssistantMessageId = null
                pendingTurnSessionId = null
                _uiState.update {
                    it.copy(
                        composerState = ComposerState.IDLE_EMPTY,
                        agentAnimState = AgentAnimState.IDLE,
                    )
                }
            }

            is StreamEvent.ApprovalRequested -> {
                val approval = PendingApproval(
                    approvalId = event.approvalId,
                    sessionId = event.sessionId,
                    description = event.description,
                )
                _uiState.update { it.copy(pendingApprovals = it.pendingApprovals + approval) }
            }

            is StreamEvent.ApprovalGranted -> {
                _uiState.update {
                    it.copy(pendingApprovals = it.pendingApprovals.filter { a -> a.approvalId != event.approvalId })
                }
            }

            is StreamEvent.ApprovalDenied -> {
                _uiState.update {
                    it.copy(pendingApprovals = it.pendingApprovals.filter { a -> a.approvalId != event.approvalId })
                }
            }

            else -> Unit
        }
    }

    private fun appendBlockToCurrentMessage(
        block: ContentBlock,
        composerState: ComposerState? = null,
        agentAnimState: AgentAnimState? = null,
    ) {
        val msgId = currentAssistantMessageId ?: return
        val sessionId = pendingTurnSessionId
        pendingTurnSessionId = null
        _uiState.update { state ->
            val messages = if (sessionId != null && state.messages.none { it.id == msgId }) {
                // Message hasn't been added yet — create it now with the first block
                val newMsg = Message(
                    id = msgId,
                    sessionId = sessionId,
                    role = MessageRole.ASSISTANT,
                    blocks = listOf(block),
                )
                state.messages + newMsg
            } else {
                state.messages.map { msg ->
                    if (msg.id == msgId) msg.copy(blocks = msg.blocks + block) else msg
                }
            }
            state.copy(
                messages = messages,
                composerState = composerState ?: state.composerState,
                agentAnimState = agentAnimState ?: state.agentAnimState,
            )
        }
    }

    private fun updateBlockInCurrentMessage(blockId: String, transform: (ContentBlock) -> ContentBlock) {
        val msgId = currentAssistantMessageId ?: return
        _uiState.update { state ->
            state.copy(
                messages = state.messages.map { msg ->
                    if (msg.id == msgId) {
                        msg.copy(blocks = msg.blocks.map { b -> if (b.blockId == blockId) transform(b) else b })
                    } else msg
                },
            )
        }
    }

    private fun updateToolBlockByToolId(toolId: String, transform: (ContentBlock.ToolBlock) -> ContentBlock.ToolBlock) {
        val msgId = currentAssistantMessageId ?: return
        _uiState.update { state ->
            state.copy(
                messages = state.messages.map { msg ->
                    if (msg.id == msgId) {
                        msg.copy(
                            blocks = msg.blocks.map { b ->
                                if (b is ContentBlock.ToolBlock && b.toolId == toolId) transform(b) else b
                            },
                        )
                    } else msg
                },
            )
        }
    }
}
