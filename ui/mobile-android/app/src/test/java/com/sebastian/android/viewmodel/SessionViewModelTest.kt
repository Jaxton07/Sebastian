package com.sebastian.android.viewmodel

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
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.times
import org.mockito.kotlin.verify
import org.mockito.kotlin.wheneverBlocking

@OptIn(ExperimentalCoroutinesApi::class)
class SessionViewModelTest {

    private lateinit var repository: SessionRepository
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setup() {
        Dispatchers.setMain(dispatcher)
        repository = mock()
        wheneverBlocking { repository.loadSessions() }.thenReturn(Result.success(emptyList()))
        wheneverBlocking { repository.loadAgentSessions(any()) }.thenReturn(Result.success(emptyList()))
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `refresh after loadAgentSessions replays agent fetch`() = runTest(dispatcher) {
        val vm = SessionViewModel(repository, dispatcher)
        advanceUntilIdle() // init { loadSessions() }

        vm.loadAgentSessions("forge")
        advanceUntilIdle()
        vm.refresh()
        advanceUntilIdle()

        verify(repository, times(2)).loadAgentSessions("forge")
    }

    @Test
    fun `refresh after loadSessions replays sebastian fetch`() = runTest(dispatcher) {
        val vm = SessionViewModel(repository, dispatcher)
        advanceUntilIdle() // init triggers loadSessions() once

        vm.refresh()
        advanceUntilIdle()

        verify(repository, times(2)).loadSessions()
    }
}

