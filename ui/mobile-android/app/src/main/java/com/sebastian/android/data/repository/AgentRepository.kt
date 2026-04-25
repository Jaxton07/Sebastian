package com.sebastian.android.data.repository

import com.sebastian.android.data.model.AgentBinding
import com.sebastian.android.data.model.AgentInfo
import com.sebastian.android.data.model.MemoryComponentInfo
import com.sebastian.android.data.model.ThinkingEffort
import com.sebastian.android.data.remote.dto.LegacyAgentBindingDto

interface AgentRepository {
    suspend fun getAgents(): Result<List<AgentInfo>>

    // ── Legacy provider-based binding (used by AgentBindingEditorViewModel until Task 3) ──
    suspend fun getBinding(agentType: String): Result<LegacyAgentBindingDto>
    suspend fun setBinding(
        agentType: String,
        providerId: String?,
        thinkingEffort: ThinkingEffort,
    ): Result<Unit>
    suspend fun clearBinding(agentType: String): Result<Unit>

    // ── Account-based agent binding ──────────────────────────────────────
    suspend fun getAgentBinding(agentType: String): Result<AgentBinding>
    suspend fun setAgentBinding(
        agentType: String,
        accountId: String?,
        modelId: String?,
        thinkingEffort: String?,
    ): Result<AgentBinding>

    // ── Memory components ────────────────────────────────────────────────
    suspend fun listMemoryComponents(): Result<List<MemoryComponentInfo>>

    // Legacy provider-based memory binding (kept until Task 3 migrates callers)
    suspend fun getMemoryComponentBinding(componentType: String): Result<LegacyAgentBindingDto>
    suspend fun setMemoryComponentBinding(
        componentType: String,
        providerId: String?,
        thinkingEffort: ThinkingEffort,
    ): Result<Unit>
    suspend fun clearMemoryComponentBinding(componentType: String): Result<Unit>

    // Account-based memory binding
    suspend fun getMemoryBinding(componentType: String): Result<AgentBinding>
    suspend fun setMemoryBinding(
        componentType: String,
        accountId: String?,
        modelId: String?,
        thinkingEffort: String?,
    ): Result<AgentBinding>
}
