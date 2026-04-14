package com.sebastian.android.viewmodel

import com.sebastian.android.data.repository.AgentRepository
import com.sebastian.android.data.repository.SessionRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.times
import org.mockito.kotlin.verify
import org.mockito.kotlin.wheneverBlocking

@OptIn(ExperimentalCoroutinesApi::class)
class SubAgentViewModelTest {

    private lateinit var agentRepository: AgentRepository
    private lateinit var sessionRepository: SessionRepository
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setup() {
        Dispatchers.setMain(dispatcher)
        agentRepository = mock()
        sessionRepository = mock()
        wheneverBlocking { agentRepository.getAgents() }.thenReturn(Result.success(emptyList()))
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `refresh re-fetches agent list`() = runTest(dispatcher) {
        val vm = SubAgentViewModel(agentRepository, sessionRepository)

        vm.loadAgents()
        advanceUntilIdle()
        vm.refresh()
        advanceUntilIdle()

        verify(agentRepository, times(2)).getAgents()
    }
}
