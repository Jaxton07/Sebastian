package com.sebastian.android.data.repository

import com.sebastian.android.data.model.AgentInfo
import com.sebastian.android.data.remote.ApiService
import com.sebastian.android.di.IoDispatcher
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AgentRepositoryImpl @Inject constructor(
    private val apiService: ApiService,
    @IoDispatcher private val dispatcher: CoroutineDispatcher,
) : AgentRepository {

    override suspend fun getAgents(): Result<List<AgentInfo>> = runCatching {
        withContext(dispatcher) {
            apiService.getAgents()
                .map { map ->
                    AgentInfo(
                        agentType = map["agent_type"]?.toString() ?: "",
                        name = map["name"]?.toString() ?: "",
                        description = map["description"]?.toString() ?: "",
                        isActive = map["is_active"] as? Boolean ?: false,
                    )
                }
                .filter { it.agentType.isNotEmpty() }
        }
    }
}
