package com.sebastian.android.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sebastian.android.data.model.CatalogProvider
import com.sebastian.android.data.model.LlmAccount
import com.sebastian.android.data.repository.SettingsRepository
import com.sebastian.android.di.IoDispatcher
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.net.URI
import javax.inject.Inject

data class ProviderFormUiState(
    val catalogProviders: List<CatalogProvider> = emptyList(),
    val selectedCatalogId: String = "",
    val name: String = "",
    val providerType: String = "anthropic",
    val baseUrl: String = "",
    val apiKey: String = "",
    val isLoading: Boolean = false,
    val isSaved: Boolean = false,
    val isDirty: Boolean = false,
    val isNew: Boolean = true,
    val hasExistingApiKey: Boolean = false,
    val createdAccountId: String? = null,
    val error: String? = null,
) {
    val isCustomMode: Boolean get() = selectedCatalogId == "custom"
}

@HiltViewModel
class ProviderFormViewModel @Inject constructor(
    private val repository: SettingsRepository,
    @param:IoDispatcher private val dispatcher: CoroutineDispatcher,
) : ViewModel() {

    private val _formState = MutableStateFlow(ProviderFormUiState())
    private val _initialSnapshot = MutableStateFlow<ProviderFormUiState?>(null)

    val uiState: StateFlow<ProviderFormUiState> = combine(
        _formState,
        _initialSnapshot,
    ) { current, initial ->
        val dirty = if (initial == null) {
            current.name.isNotBlank() || current.apiKey.isNotBlank() ||
                current.baseUrl.isNotBlank() || current.selectedCatalogId.isNotBlank()
        } else {
            current.name.trim() != initial.name.trim() ||
                current.apiKey.trim() != initial.apiKey.trim() ||
                current.baseUrl.trim() != initial.baseUrl.trim() ||
                current.selectedCatalogId != initial.selectedCatalogId ||
                current.providerType != initial.providerType
        }
        current.copy(isDirty = dirty, isNew = initial == null)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), ProviderFormUiState())

    init {
        loadCatalog()
    }

    private fun loadCatalog() {
        viewModelScope.launch(dispatcher) {
            repository.getLlmCatalog()
                .onSuccess { catalog ->
                    _formState.update { it.copy(catalogProviders = catalog) }
                }
        }
    }

    fun loadAccount(accountId: String) {
        viewModelScope.launch(dispatcher) {
            repository.getLlmAccounts()
                .onSuccess { accounts ->
                    val account = accounts.find { it.id == accountId } ?: return@launch
                    val loaded = ProviderFormUiState(
                        selectedCatalogId = account.catalogProviderId,
                        name = account.name,
                        providerType = account.providerType,
                        baseUrl = account.baseUrlOverride ?: "",
                        hasExistingApiKey = account.hasApiKey,
                        createdAccountId = account.id,
                    )
                    _formState.value = loaded
                    _initialSnapshot.value = loaded
                }
                .onFailure { e -> _formState.update { it.copy(error = e.message) } }
        }
    }

    fun onCatalogSelect(id: String) = _formState.update { it.copy(selectedCatalogId = id) }
    fun onNameChange(v: String) = _formState.update { it.copy(name = v) }
    fun onProviderTypeChange(v: String) = _formState.update { it.copy(providerType = v) }
    fun onBaseUrlChange(v: String) = _formState.update { it.copy(baseUrl = v) }
    fun onApiKeyChange(v: String) = _formState.update { it.copy(apiKey = v) }

    fun save(existingId: String?) {
        val state = _formState.value
        if (state.name.isBlank()) {
            _formState.update { it.copy(error = "名称不能为空") }
            return
        }
        if (state.isCustomMode) {
            if (state.baseUrl.isBlank()) {
                _formState.update { it.copy(error = "Base URL 不能为空") }
                return
            }
            if (!isValidBaseUrl(state.baseUrl)) {
                _formState.update { it.copy(error = "Base URL 必须是 http(s) 地址") }
                return
            }
        }
        val requireApiKey = existingId == null || state.apiKey.isNotBlank()
        if (requireApiKey && state.apiKey.isBlank()) {
            _formState.update { it.copy(error = "API Key 不能为空") }
            return
        }

        viewModelScope.launch(dispatcher) {
            _formState.update { it.copy(isLoading = true, error = null) }
            val catalogId = if (state.isCustomMode) "custom" else state.selectedCatalogId
            val apiKeyToSend = state.apiKey.trim().ifEmpty { null }

            val result = if (existingId == null) {
                repository.createLlmAccount(
                    name = state.name.trim(),
                    catalogProviderId = catalogId,
                    apiKey = apiKeyToSend ?: "",
                    providerType = if (state.isCustomMode) state.providerType else null,
                    baseUrlOverride = if (state.isCustomMode) state.baseUrl.trim() else null,
                )
            } else {
                repository.updateLlmAccount(
                    accountId = existingId,
                    name = state.name.trim(),
                    apiKey = apiKeyToSend,
                    baseUrlOverride = if (state.isCustomMode) state.baseUrl.trim().ifEmpty { null } else null,
                )
            }
            result
                .onSuccess { account ->
                    _formState.update {
                        it.copy(
                            isLoading = false,
                            isSaved = true,
                            createdAccountId = account.id,
                        )
                    }
                }
                .onFailure { e -> _formState.update { it.copy(isLoading = false, error = e.message) } }
        }
    }

    fun clearError() = _formState.update { it.copy(error = null) }

    private fun isValidBaseUrl(value: String): Boolean {
        val uri = runCatching { URI(value.trim()) }.getOrNull() ?: return false
        val scheme = uri.scheme ?: return false
        val hasHttpScheme = scheme.equals("http", ignoreCase = true) ||
            scheme.equals("https", ignoreCase = true)
        return hasHttpScheme && !uri.host.isNullOrBlank()
    }
}
