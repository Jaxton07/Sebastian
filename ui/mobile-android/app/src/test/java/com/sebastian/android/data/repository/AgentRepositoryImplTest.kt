package com.sebastian.android.data.repository

import com.sebastian.android.data.model.ThinkingEffort
import com.sebastian.android.data.remote.ApiService
import com.sebastian.android.data.remote.dto.AgentBindingDto
import com.sebastian.android.data.remote.dto.LegacyAgentBindingDto
import com.sebastian.android.data.remote.dto.LegacySetBindingRequest
import com.sebastian.android.data.remote.dto.MemoryComponentBindingDto
import com.sebastian.android.data.remote.dto.MemoryComponentDto
import com.sebastian.android.data.remote.dto.MemoryComponentsResponse
import com.sebastian.android.data.remote.dto.SetBindingRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.Mockito.mock
import org.mockito.Mockito.verify
import org.mockito.Mockito.`when`
import org.mockito.kotlin.any
import org.mockito.kotlin.argumentCaptor
import org.mockito.kotlin.eq

class AgentRepositoryImplTest {

    @Test
    fun `setBinding sends provider_id and OFF effort as null thinking_effort`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.setAgentBinding(eq("forge"), any())).thenReturn(
            LegacyAgentBindingDto(agentType = "forge", providerId = "p1", thinkingEffort = null)
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.setBinding("forge", "p1", ThinkingEffort.OFF)

        assertTrue(result.isSuccess)
        val captor = argumentCaptor<LegacySetBindingRequest>()
        verify(api).setAgentBinding(eq("forge"), captor.capture())
        assertEquals("p1", captor.firstValue.providerId)
        assertNull(captor.firstValue.thinkingEffort)
    }

    @Test
    fun `setBinding maps HIGH effort to high string in request body`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.setAgentBinding(eq("forge"), any())).thenReturn(
            LegacyAgentBindingDto(agentType = "forge", providerId = "p1", thinkingEffort = "high")
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        repo.setBinding("forge", "p1", ThinkingEffort.HIGH)

        val captor = argumentCaptor<LegacySetBindingRequest>()
        verify(api).setAgentBinding(eq("forge"), captor.capture())
        assertEquals("high", captor.firstValue.thinkingEffort)
    }

    @Test
    fun `setBinding allows null provider_id for use-default`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.setAgentBinding(eq("forge"), any())).thenReturn(
            LegacyAgentBindingDto(agentType = "forge", providerId = null, thinkingEffort = null)
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        repo.setBinding("forge", null, ThinkingEffort.OFF)

        val captor = argumentCaptor<LegacySetBindingRequest>()
        verify(api).setAgentBinding(eq("forge"), captor.capture())
        assertNull(captor.firstValue.providerId)
    }

    @Test
    fun `clearBinding calls clearAgentBinding and returns success`() = runTest {
        val api = mock(ApiService::class.java)
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.clearBinding("forge")
        assertTrue(result.isSuccess)
        verify(api).clearAgentBinding("forge")
    }

    // ── Memory Component tests ──────────────────────────────────────────────

    @Test
    fun `listMemoryComponents maps null binding to null boundAccountId and OFF effort`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.listMemoryComponents()).thenReturn(
            MemoryComponentsResponse(
                components = listOf(
                    MemoryComponentDto(
                        componentType = "episodic",
                        displayName = "Episodic Memory",
                        description = "Stores episodic events",
                        binding = null,
                    )
                )
            )
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.listMemoryComponents()

        assertTrue(result.isSuccess)
        val components = result.getOrThrow()
        assertEquals(1, components.size)
        val info = components[0]
        assertEquals("episodic", info.componentType)
        assertNull(info.boundAccountId)
        assertEquals(ThinkingEffort.OFF, info.thinkingEffort)
    }

    @Test
    fun `listMemoryComponents maps binding to correct boundAccountId and thinkingEffort`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.listMemoryComponents()).thenReturn(
            MemoryComponentsResponse(
                components = listOf(
                    MemoryComponentDto(
                        componentType = "semantic",
                        displayName = "Semantic Memory",
                        description = "Stores semantic facts",
                        binding = MemoryComponentBindingDto(
                            componentType = "semantic",
                            accountId = "acct-42",
                            modelId = "claude-3-5-sonnet",
                            thinkingEffort = "high",
                        ),
                    )
                )
            )
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.listMemoryComponents()

        assertTrue(result.isSuccess)
        val info = result.getOrThrow()[0]
        assertEquals("acct-42", info.boundAccountId)
        assertEquals(ThinkingEffort.HIGH, info.thinkingEffort)
    }

    @Test
    fun `getMemoryComponentBinding fills agentType with componentType`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.getMemoryComponentBinding("episodic")).thenReturn(
            MemoryComponentBindingDto(
                componentType = "episodic",
                accountId = "acct-1",
                thinkingEffort = null,
            )
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.getMemoryComponentBinding("episodic")

        assertTrue(result.isSuccess)
        val dto = result.getOrThrow()
        assertEquals("episodic", dto.agentType)
        // Legacy getMemoryComponentBinding maps accountId -> providerId for backward compat
        assertEquals("acct-1", dto.providerId)
        assertNull(dto.thinkingEffort)
    }

    @Test
    fun `setMemoryComponentBinding sends correct request with OFF effort as null`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.setMemoryComponentBinding(eq("semantic"), any())).thenReturn(
            MemoryComponentBindingDto(componentType = "semantic", accountId = "acct-2", thinkingEffort = null)
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.setMemoryComponentBinding("semantic", "acct-2", ThinkingEffort.OFF)

        assertTrue(result.isSuccess)
        val captor = argumentCaptor<LegacySetBindingRequest>()
        verify(api).setMemoryComponentBinding(eq("semantic"), captor.capture())
        assertEquals("acct-2", captor.firstValue.providerId)
        assertNull(captor.firstValue.thinkingEffort)
    }

    @Test
    fun `setMemoryComponentBinding maps HIGH effort to high string`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.setMemoryComponentBinding(eq("semantic"), any())).thenReturn(
            MemoryComponentBindingDto(componentType = "semantic", accountId = "acct-2", thinkingEffort = "high")
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        repo.setMemoryComponentBinding("semantic", "acct-2", ThinkingEffort.HIGH)

        val captor = argumentCaptor<LegacySetBindingRequest>()
        verify(api).setMemoryComponentBinding(eq("semantic"), captor.capture())
        assertEquals("high", captor.firstValue.thinkingEffort)
    }

    @Test
    fun `clearMemoryComponentBinding calls correct API endpoint and returns success`() = runTest {
        val api = mock(ApiService::class.java)
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.clearMemoryComponentBinding("episodic")

        assertTrue(result.isSuccess)
        verify(api).clearMemoryComponentBinding("episodic")
    }

    // ── Account-based memory binding tests ──────────────────────────────────

    @Test
    fun `getMemoryBinding returns AgentBinding with accountId and modelId`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.getMemoryComponentBindingV2("episodic")).thenReturn(
            MemoryComponentBindingDto(
                componentType = "episodic",
                accountId = "acct-1",
                modelId = "claude-3-5-sonnet",
                thinkingEffort = "medium",
            )
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.getMemoryBinding("episodic")

        assertTrue(result.isSuccess)
        val binding = result.getOrThrow()
        assertEquals("episodic", binding.agentType)
        assertEquals("acct-1", binding.accountId)
        assertEquals("claude-3-5-sonnet", binding.modelId)
        assertEquals("medium", binding.thinkingEffort)
    }

    @Test
    fun `setMemoryBinding sends accountId and modelId in request`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.setMemoryComponentBindingV2(eq("semantic"), any())).thenReturn(
            MemoryComponentBindingDto(
                componentType = "semantic",
                accountId = "acct-5",
                modelId = "claude-opus-4",
                thinkingEffort = "high",
            )
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.setMemoryBinding("semantic", "acct-5", "claude-opus-4", "high")

        assertTrue(result.isSuccess)
        val captor = argumentCaptor<SetBindingRequest>()
        verify(api).setMemoryComponentBindingV2(eq("semantic"), captor.capture())
        assertEquals("acct-5", captor.firstValue.accountId)
        assertEquals("claude-opus-4", captor.firstValue.modelId)
        assertEquals("high", captor.firstValue.thinkingEffort)
    }

    @Test
    fun `getAgentBinding returns AgentBinding via V2 endpoint`() = runTest {
        val api = mock(ApiService::class.java)
        `when`(api.getAgentBindingV2("forge")).thenReturn(
            AgentBindingDto(
                agentType = "forge",
                accountId = "acct-7",
                modelId = "claude-3-5-sonnet",
                thinkingEffort = null,
            )
        )
        val repo = AgentRepositoryImpl(api, Dispatchers.Unconfined)

        val result = repo.getAgentBinding("forge")

        assertTrue(result.isSuccess)
        val binding = result.getOrThrow()
        assertEquals("forge", binding.agentType)
        assertEquals("acct-7", binding.accountId)
        assertEquals("claude-3-5-sonnet", binding.modelId)
    }
}
