package com.sebastian.android.data.repository

import com.sebastian.android.data.model.AgentBinding
import com.sebastian.android.data.model.AgentInfo
import com.sebastian.android.data.model.MemoryComponentInfo

interface AgentRepository {
    suspend fun getAgents(): Result<List<AgentInfo>>

    // ── Account-based agent binding ──────────────────────────────────────────
    suspend fun getAgentBinding(agentType: String): Result<AgentBinding>
    suspend fun setAgentBinding(
        agentType: String,
        accountId: String?,
        modelId: String?,
        thinkingEffort: String?,
    ): Result<AgentBinding>
    suspend fun clearAgentBinding(agentType: String): Result<Unit>

    // ── Memory components ────────────────────────────────────────────────────
    suspend fun listMemoryComponents(): Result<List<MemoryComponentInfo>>

    // Account-based memory binding
    suspend fun getMemoryBinding(componentType: String): Result<AgentBinding>
    suspend fun setMemoryBinding(
        componentType: String,
        accountId: String?,
        modelId: String?,
        thinkingEffort: String?,
    ): Result<AgentBinding>
    suspend fun clearMemoryComponentBinding(componentType: String): Result<Unit>
}
