package com.sebastian.android.data.remote.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class MemorySettingsDto(
    @param:Json(name = "enabled") val enabled: Boolean,
)
