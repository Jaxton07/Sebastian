package com.sebastian.android.data.repository

import com.sebastian.android.data.model.AgentBinding
import com.sebastian.android.data.model.AgentInfo
import com.sebastian.android.data.model.MemoryComponentInfo
import com.sebastian.android.data.remote.ApiService
import com.sebastian.android.data.remote.dto.SetBindingRequest
import com.sebastian.android.data.remote.dto.toAgentBinding
import com.sebastian.android.di.IoDispatcher
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AgentRepositoryImpl @Inject constructor(
    private val apiService: ApiService,
    @param:IoDispatcher private val dispatcher: CoroutineDispatcher,
) : AgentRepository {

    override suspend fun getAgents(): Result<List<AgentInfo>> = runCatching {
        withContext(dispatcher) {
            apiService.getAgents().agents.map { it.toDomain() }
        }
    }

    // ── Account-based agent binding ──────────────────────────────────────────

    override suspend fun getAgentBinding(agentType: String): Result<AgentBinding> = runCatching {
        withContext(dispatcher) {
            apiService.getAgentBinding(agentType).toDomain()
        }
    }

    override suspend fun setAgentBinding(
        agentType: String,
        accountId: String?,
        modelId: String?,
        thinkingEffort: String?,
    ): Result<AgentBinding> = runCatching {
        withContext(dispatcher) {
            apiService.setAgentBinding(
                agentType,
                SetBindingRequest(
                    accountId = accountId,
                    modelId = modelId,
                    thinkingEffort = thinkingEffort,
                ),
            ).toDomain()
        }
    }

    override suspend fun clearAgentBinding(agentType: String): Result<Unit> = runCatching {
        withContext(dispatcher) {
            apiService.clearAgentBinding(agentType)
        }
    }

    // ── Memory components ────────────────────────────────────────────────────

    override suspend fun listMemoryComponents(): Result<List<MemoryComponentInfo>> = runCatching {
        withContext(dispatcher) {
            apiService.listMemoryComponents().components.map { it.toDomain() }
        }
    }

    // Account-based memory binding

    override suspend fun getMemoryBinding(componentType: String): Result<AgentBinding> = runCatching {
        withContext(dispatcher) {
            apiService.getMemoryComponentBinding(componentType).toAgentBinding(componentType)
        }
    }

    override suspend fun setMemoryBinding(
        componentType: String,
        accountId: String?,
        modelId: String?,
        thinkingEffort: String?,
    ): Result<AgentBinding> = runCatching {
        withContext(dispatcher) {
            apiService.setMemoryComponentBinding(
                componentType,
                SetBindingRequest(
                    accountId = accountId,
                    modelId = modelId,
                    thinkingEffort = thinkingEffort,
                ),
            ).toAgentBinding(componentType)
        }
    }

    override suspend fun clearMemoryComponentBinding(componentType: String): Result<Unit> = runCatching {
        withContext(dispatcher) {
            apiService.clearMemoryComponentBinding(componentType)
        }
    }
}
