package com.sebastian.android.data.remote

import app.cash.turbine.test
import com.sebastian.android.data.model.StreamEvent
import com.sebastian.android.data.repository.ChatRepository
import com.sebastian.android.data.repository.SettingsRepository
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever

@OptIn(ExperimentalCoroutinesApi::class)
class GlobalSseDispatcherTest {

    private suspend fun buildSettings(url: String): SettingsRepository =
        mock<SettingsRepository>().also { whenever(it.readServerUrl()).thenReturn(url) }

    @Test
    fun `events flow fans out to multiple subscribers`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val upstream = MutableSharedFlow<SseEnvelope>(extraBufferCapacity = 64)
        val chatRepo = mock<ChatRepository>()
        val settings = buildSettings("http://x")
        whenever(chatRepo.globalStream("http://x", null)).thenReturn(upstream)

        val sut = GlobalSseDispatcher(chatRepo, settings, dispatcher)
        val scope = TestScope(dispatcher)

        val received1 = mutableListOf<StreamEvent>()
        val received2 = mutableListOf<StreamEvent>()
        val job1 = scope.launch { sut.events.collect { received1 += it } }
        val job2 = scope.launch { sut.events.collect { received2 += it } }

        sut.start(scope)
        testScheduler.advanceUntilIdle()

        upstream.emit(SseEnvelope(eventId = "1", event = StreamEvent.ApprovalGranted("a1")))
        testScheduler.advanceUntilIdle()

        assertEquals(listOf(StreamEvent.ApprovalGranted("a1")), received1)
        assertEquals(listOf(StreamEvent.ApprovalGranted("a1")), received2)

        job1.cancel()
        job2.cancel()
        sut.stop()
    }

    @Test
    fun `connectionState reports Connected when upstream emits first event`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val upstream = MutableSharedFlow<SseEnvelope>(extraBufferCapacity = 64)
        val chatRepo = mock<ChatRepository>()
        val settings = buildSettings("http://x")
        whenever(chatRepo.globalStream("http://x", null)).thenReturn(upstream)

        val sut = GlobalSseDispatcher(chatRepo, settings, dispatcher)
        val scope = TestScope(dispatcher)

        sut.connectionState.test {
            assertEquals(ConnectionState.Disconnected, awaitItem())
            sut.start(scope)
            testScheduler.advanceUntilIdle()
            assertEquals(ConnectionState.Connecting, awaitItem())

            upstream.emit(SseEnvelope(eventId = "1", event = StreamEvent.ApprovalGranted("a1")))
            testScheduler.advanceUntilIdle()
            assertEquals(ConnectionState.Connected, awaitItem())

            sut.stop()
            testScheduler.advanceUntilIdle()
            assertEquals(ConnectionState.Disconnected, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test
    fun `start does not connect when readServerUrl returns blank`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val chatRepo = mock<ChatRepository>()
        val settings = buildSettings("")

        val sut = GlobalSseDispatcher(chatRepo, settings, dispatcher)
        val scope = TestScope(dispatcher)

        sut.start(scope)
        testScheduler.advanceUntilIdle()

        verify(chatRepo, never()).globalStream(org.mockito.kotlin.any(), org.mockito.kotlin.anyOrNull())
        assertFalse(sut.connectionState.value == ConnectionState.Connecting)
    }
}
