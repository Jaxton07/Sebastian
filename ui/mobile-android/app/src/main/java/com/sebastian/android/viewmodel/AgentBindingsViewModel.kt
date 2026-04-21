package com.sebastian.android.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sebastian.android.data.model.AgentInfo
import com.sebastian.android.data.model.MemoryComponentInfo
import com.sebastian.android.data.model.Provider
import com.sebastian.android.data.repository.AgentRepository
import com.sebastian.android.data.repository.SettingsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AgentBindingsUiState(
    val loading: Boolean = false,
    val agents: List<AgentInfo> = emptyList(),
    val memoryComponents: List<MemoryComponentInfo> = emptyList(),
    val providers: List<Provider> = emptyList(),
    val errorMessage: String? = null,
)

@HiltViewModel
class AgentBindingsViewModel @Inject constructor(
    private val agentRepository: AgentRepository,
    private val settingsRepository: SettingsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AgentBindingsUiState())
    val uiState: StateFlow<AgentBindingsUiState> = _uiState

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, errorMessage = null) }
            val agentsD = async { agentRepository.getAgents() }
            val componentsD = async { agentRepository.listMemoryComponents() }
            val providersD = async { settingsRepository.getProviders() }
            val agentsR = agentsD.await()
            val componentsR = componentsD.await()
            val providersR = providersD.await()
            val err = agentsR.exceptionOrNull()
                ?: componentsR.exceptionOrNull()
                ?: providersR.exceptionOrNull()
            _uiState.update {
                it.copy(
                    loading = false,
                    agents = agentsR.getOrDefault(emptyList()),
                    memoryComponents = componentsR.getOrDefault(emptyList()),
                    providers = providersR.getOrDefault(emptyList()),
                    errorMessage = err?.message,
                )
            }
        }
    }
}
