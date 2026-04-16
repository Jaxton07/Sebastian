package com.sebastian.android.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sebastian.android.data.model.AgentInfo
import com.sebastian.android.data.model.Provider
import com.sebastian.android.data.repository.AgentRepository
import com.sebastian.android.data.repository.SettingsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AgentBindingsUiState(
    val loading: Boolean = false,
    val agents: List<AgentInfo> = emptyList(),
    val providers: List<Provider> = emptyList(),
    val errorMessage: String? = null,
)

sealed interface AgentBindingsEvent {
    data object BindingUpdated : AgentBindingsEvent
    data class Error(val message: String) : AgentBindingsEvent
}

@HiltViewModel
class AgentBindingsViewModel @Inject constructor(
    private val agentRepository: AgentRepository,
    private val settingsRepository: SettingsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AgentBindingsUiState())
    val uiState: StateFlow<AgentBindingsUiState> = _uiState

    private val _events = MutableSharedFlow<AgentBindingsEvent>(replay = 1)
    val events: SharedFlow<AgentBindingsEvent> = _events.asSharedFlow()

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, errorMessage = null) }
            val agentsResult = agentRepository.getAgents()
            val providersResult = settingsRepository.getProviders()
            val err = agentsResult.exceptionOrNull() ?: providersResult.exceptionOrNull()
            _uiState.update {
                it.copy(
                    loading = false,
                    agents = agentsResult.getOrDefault(emptyList()),
                    providers = providersResult.getOrDefault(emptyList()),
                    errorMessage = err?.message,
                )
            }
        }
    }

    fun bind(agentType: String, providerId: String) {
        viewModelScope.launch {
            val result = agentRepository.setBinding(agentType, providerId)
            result.fold(
                onSuccess = {
                    _uiState.update { state ->
                        state.copy(
                            agents = state.agents.map { a ->
                                if (a.agentType == agentType) a.copy(boundProviderId = providerId) else a
                            }
                        )
                    }
                    _events.tryEmit(AgentBindingsEvent.BindingUpdated)
                },
                onFailure = {
                    _events.tryEmit(AgentBindingsEvent.Error(it.message.orEmpty()))
                }
            )
        }
    }

    fun useDefault(agentType: String) {
        viewModelScope.launch {
            val result = agentRepository.clearBinding(agentType)
            result.fold(
                onSuccess = {
                    _uiState.update { state ->
                        state.copy(
                            agents = state.agents.map { a ->
                                if (a.agentType == agentType) a.copy(boundProviderId = null) else a
                            }
                        )
                    }
                    _events.tryEmit(AgentBindingsEvent.BindingUpdated)
                },
                onFailure = {
                    _events.tryEmit(AgentBindingsEvent.Error(it.message.orEmpty()))
                }
            )
        }
    }
}
