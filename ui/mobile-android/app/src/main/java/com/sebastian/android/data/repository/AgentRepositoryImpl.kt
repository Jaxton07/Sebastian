package com.sebastian.android.data.repository

import com.sebastian.android.data.model.AgentBinding
import com.sebastian.android.data.model.AgentInfo
import com.sebastian.android.data.model.MemoryComponentInfo
import com.sebastian.android.data.model.ThinkingEffort
import com.sebastian.android.data.model.toApiString
import com.sebastian.android.data.remote.ApiService
import com.sebastian.android.data.remote.dto.AgentBindingDto
import com.sebastian.android.data.remote.dto.LegacyAgentBindingDto
import com.sebastian.android.data.remote.dto.LegacySetBindingRequest
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

    // ── Legacy provider-based agent binding ──────────────────────────────

    override suspend fun getBinding(agentType: String): Result<LegacyAgentBindingDto> = runCatching {
        withContext(dispatcher) {
            apiService.getAgentBinding(agentType)
        }
    }

    override suspend fun setBinding(
        agentType: String,
        providerId: String?,
        thinkingEffort: ThinkingEffort,
    ): Result<Unit> = runCatching {
        withContext(dispatcher) {
            apiService.setAgentBinding(
                agentType,
                LegacySetBindingRequest(
                    providerId = providerId,
                    thinkingEffort = thinkingEffort.toApiString(),
                ),
            )
            Unit
        }
    }

    override suspend fun clearBinding(agentType: String): Result<Unit> = runCatching {
        withContext(dispatcher) {
            apiService.clearAgentBinding(agentType)
        }
    }

    // ── Account-based agent binding ──────────────────────────────────────

    override suspend fun getAgentBinding(agentType: String): Result<AgentBinding> = runCatching {
        withContext(dispatcher) {
            apiService.getAgentBindingV2(agentType).toDomain()
        }
    }

    override suspend fun setAgentBinding(
        agentType: String,
        accountId: String?,
        modelId: String?,
        thinkingEffort: String?,
    ): Result<AgentBinding> = runCatching {
        withContext(dispatcher) {
            apiService.setAgentBindingV2(
                agentType,
                SetBindingRequest(
                    accountId = accountId,
                    modelId = modelId,
                    thinkingEffort = thinkingEffort,
                ),
            ).toDomain()
        }
    }

    // ── Memory components ────────────────────────────────────────────────

    override suspend fun listMemoryComponents(): Result<List<MemoryComponentInfo>> = runCatching {
        withContext(dispatcher) {
            apiService.listMemoryComponents().components.map { it.toDomain() }
        }
    }

    // Legacy provider-based memory binding

    override suspend fun getMemoryComponentBinding(
        componentType: String,
    ): Result<LegacyAgentBindingDto> = runCatching {
        withContext(dispatcher) {
            val dto = apiService.getMemoryComponentBinding(componentType)
            LegacyAgentBindingDto(
                agentType = dto.componentType ?: componentType,
                providerId = dto.accountId,
                thinkingEffort = dto.thinkingEffort,
            )
        }
    }

    override suspend fun setMemoryComponentBinding(
        componentType: String,
        providerId: String?,
        thinkingEffort: ThinkingEffort,
    ): Result<Unit> = runCatching {
        withContext(dispatcher) {
            apiService.setMemoryComponentBinding(
                componentType,
                LegacySetBindingRequest(
                    providerId = providerId,
                    thinkingEffort = thinkingEffort.toApiString(),
                ),
            )
            Unit
        }
    }

    override suspend fun clearMemoryComponentBinding(
        componentType: String,
    ): Result<Unit> = runCatching {
        withContext(dispatcher) {
            apiService.clearMemoryComponentBinding(componentType)
        }
    }

    // Account-based memory binding

    override suspend fun getMemoryBinding(componentType: String): Result<AgentBinding> = runCatching {
        withContext(dispatcher) {
            apiService.getMemoryComponentBindingV2(componentType).toAgentBinding(componentType)
        }
    }

    override suspend fun setMemoryBinding(
        componentType: String,
        accountId: String?,
        modelId: String?,
        thinkingEffort: String?,
    ): Result<AgentBinding> = runCatching {
        withContext(dispatcher) {
            apiService.setMemoryComponentBindingV2(
                componentType,
                SetBindingRequest(
                    accountId = accountId,
                    modelId = modelId,
                    thinkingEffort = thinkingEffort,
                ),
            ).toAgentBinding(componentType)
        }
    }
}
