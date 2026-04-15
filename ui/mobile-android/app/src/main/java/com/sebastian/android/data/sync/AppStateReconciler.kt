package com.sebastian.android.data.sync

import com.sebastian.android.data.repository.ChatRepository
import com.sebastian.android.di.IoDispatcher
import com.sebastian.android.viewmodel.GlobalApprovalViewModel
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AppStateReconciler @Inject constructor(
    private val chatRepository: ChatRepository,
    @IoDispatcher private val defaultDispatcher: CoroutineDispatcher,
) {
    private var approvalViewModelProvider: (() -> GlobalApprovalViewModel)? = null
    private var reconcileChatSession: (suspend () -> Unit)? = null
    private var externalScope: CoroutineScope? = null
    private var pendingJob: Job? = null
    private var debounceMs: Long = 150L
    private var dispatcher: CoroutineDispatcher = defaultDispatcher

    /** 测试专用构造 */
    internal constructor(
        chatRepository: ChatRepository,
        approvalViewModelProvider: () -> GlobalApprovalViewModel,
        reconcileChatSession: suspend () -> Unit,
        debounceMs: Long,
        dispatcher: CoroutineDispatcher,
    ) : this(chatRepository, dispatcher) {
        this.approvalViewModelProvider = approvalViewModelProvider
        this.reconcileChatSession = reconcileChatSession
        this.debounceMs = debounceMs
        this.dispatcher = dispatcher
    }

    fun attach(
        scope: CoroutineScope,
        approvalViewModelProvider: () -> GlobalApprovalViewModel,
        reconcileChatSession: suspend () -> Unit,
    ) {
        this.externalScope = scope
        this.approvalViewModelProvider = approvalViewModelProvider
        this.reconcileChatSession = reconcileChatSession
    }

    /** 测试专用 attach 重载 */
    internal fun attach(scope: CoroutineScope) {
        this.externalScope = scope
    }

    fun reconcile() {
        val scope = externalScope ?: return
        pendingJob?.cancel()
        pendingJob = scope.launch(dispatcher) {
            delay(debounceMs)
            runReconcile()
        }
    }

    private suspend fun runReconcile() = coroutineScope {
        val approvalsDeferred = async {
            chatRepository.getPendingApprovals().getOrNull() ?: emptyList()
        }
        val chatReconcileDeferred = async { reconcileChatSession?.invoke() }
        val approvals = approvalsDeferred.await()
        approvalViewModelProvider?.invoke()?.replaceAll(approvals)
        chatReconcileDeferred.await()
    }
}
