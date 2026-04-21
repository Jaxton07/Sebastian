package com.sebastian.android.viewmodel

import com.sebastian.android.data.remote.dto.MemorySettingsDto
import com.sebastian.android.data.repository.SettingsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.wheneverBlocking

@OptIn(ExperimentalCoroutinesApi::class)
class MemorySettingsViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private lateinit var repository: SettingsRepository
    private lateinit var viewModel: MemorySettingsViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        repository = mock()
        wheneverBlocking { repository.getMemorySettings() }
            .thenReturn(Result.success(MemorySettingsDto(enabled = true)))
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `init loads memory settings and updates enabled state`() = runTest(dispatcher) {
        wheneverBlocking { repository.getMemorySettings() }
            .thenReturn(Result.success(MemorySettingsDto(enabled = false)))
        viewModel = MemorySettingsViewModel(repository, dispatcher)
        advanceUntilIdle()

        assertEquals(false, viewModel.uiState.value.enabled)
        assertEquals(false, viewModel.uiState.value.isLoading)
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun `toggle success updates enabled state`() = runTest(dispatcher) {
        wheneverBlocking { repository.setMemoryEnabled(false) }
            .thenReturn(Result.success(MemorySettingsDto(enabled = false)))
        viewModel = MemorySettingsViewModel(repository, dispatcher)
        advanceUntilIdle()   // let init complete

        viewModel.toggle(false)
        // verify optimistic update applied immediately
        assertEquals(false, viewModel.uiState.value.enabled)
        assertEquals(true, viewModel.uiState.value.isLoading)

        advanceUntilIdle()   // let network call complete
        assertEquals(false, viewModel.uiState.value.enabled)
        assertEquals(false, viewModel.uiState.value.isLoading)
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun `toggle failure rolls back state and sets error`() = runTest(dispatcher) {
        wheneverBlocking { repository.setMemoryEnabled(false) }
            .thenReturn(Result.failure(Exception("network error")))
        viewModel = MemorySettingsViewModel(repository, dispatcher)
        advanceUntilIdle()   // let init complete (enabled = true)

        viewModel.toggle(false)
        advanceUntilIdle()

        assertEquals(true, viewModel.uiState.value.enabled)  // rolled back
        assertEquals(false, viewModel.uiState.value.isLoading)
        assertNotNull(viewModel.uiState.value.error)
    }

    @Test
    fun `clearError resets error to null`() = runTest(dispatcher) {
        wheneverBlocking { repository.setMemoryEnabled(false) }
            .thenReturn(Result.failure(Exception("network error")))
        viewModel = MemorySettingsViewModel(repository, dispatcher)
        advanceUntilIdle()

        viewModel.toggle(false)
        advanceUntilIdle()
        assertNotNull(viewModel.uiState.value.error)

        viewModel.clearError()
        assertNull(viewModel.uiState.value.error)
    }
}
