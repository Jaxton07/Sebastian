package com.sebastian.android.data.remote.dto

import com.sebastian.android.data.model.AgentBinding
import com.sebastian.android.data.model.MemoryComponentInfo
import com.sebastian.android.data.model.toThinkingEffort
import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class MemoryComponentBindingDto(
    @param:Json(name = "component_type") val componentType: String? = null,
    @param:Json(name = "account_id") val accountId: String? = null,
    @param:Json(name = "model_id") val modelId: String? = null,
    @param:Json(name = "thinking_effort") val thinkingEffort: String? = null,
    @param:Json(name = "resolved") val resolved: ResolvedBindingDto? = null,
)

fun MemoryComponentBindingDto.toAgentBinding(componentTypeFallback: String) = AgentBinding(
    agentType = componentType ?: componentTypeFallback,
    accountId = accountId,
    modelId = modelId,
    thinkingEffort = thinkingEffort,
    resolved = resolved?.toDomain(),
)

@JsonClass(generateAdapter = true)
data class MemoryComponentDto(
    @param:Json(name = "component_type") val componentType: String,
    @param:Json(name = "display_name") val displayName: String,
    val description: String,
    val binding: MemoryComponentBindingDto?,
) {
    fun toDomain() = MemoryComponentInfo(
        componentType = componentType,
        displayName = displayName,
        description = description,
        boundAccountId = binding?.accountId,
        boundModelId = binding?.modelId,
        thinkingEffort = binding?.thinkingEffort.toThinkingEffort(),
    )
}

@JsonClass(generateAdapter = true)
data class MemoryComponentsResponse(
    val components: List<MemoryComponentDto>,
)
