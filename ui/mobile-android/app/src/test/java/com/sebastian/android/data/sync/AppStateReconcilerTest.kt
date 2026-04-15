package com.sebastian.android.data.sync

import com.sebastian.android.data.repository.ChatRepository
import com.sebastian.android.viewmodel.GlobalApprovalViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.times
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever

@OptIn(ExperimentalCoroutinesApi::class)
class AppStateReconcilerTest {

    @Test
    fun `three rapid calls collapse to one REST fetch after debounce`() = runTest {
        val chatRepo: ChatRepository = mock()
        whenever(chatRepo.getPendingApprovals()).thenReturn(Result.success(emptyList()))
        val approvalVm: GlobalApprovalViewModel = mock()

        val reconciler = AppStateReconciler(
            chatRepository = chatRepo,
            approvalViewModelProvider = { approvalVm },
            debounceMs = 150L,
            dispatcher = StandardTestDispatcher(testScheduler),
        )
        reconciler.attach(TestScope(testScheduler))

        reconciler.reconcile()
        advanceTimeBy(50)
        reconciler.reconcile()
        advanceTimeBy(50)
        reconciler.reconcile()
        advanceUntilIdle()

        verify(chatRepo, times(1)).getPendingApprovals()
        verify(approvalVm, times(1)).replaceAll(emptyList())
    }
}
