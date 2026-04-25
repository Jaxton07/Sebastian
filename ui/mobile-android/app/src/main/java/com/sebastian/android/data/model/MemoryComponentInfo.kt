package com.sebastian.android.data.model

data class MemoryComponentInfo(
    val componentType: String,
    val displayName: String,
    val description: String,
    val boundAccountId: String? = null,
    val boundModelId: String? = null,
    val thinkingEffort: ThinkingEffort = ThinkingEffort.OFF,
) {
    /** Legacy alias kept for test and UI compatibility until callers migrate. */
    val boundProviderId: String? get() = boundAccountId
}
