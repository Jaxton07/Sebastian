package com.sebastian.android.data.model

data class MemoryComponentInfo(
    val componentType: String,
    val displayName: String,
    val description: String,
    val boundAccountId: String? = null,
    val boundModelId: String? = null,
    val boundAccountName: String? = null,
    val boundModelDisplayName: String? = null,
    val thinkingEffort: ThinkingEffort = ThinkingEffort.OFF,
)
