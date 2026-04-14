package com.sebastian.android.ui.chat

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ToolDisplayNameTest {

    @Test
    fun `delegate_to_agent title capitalizes agent_type, summary empty`() {
        val display = ToolDisplayName.resolve(
            "delegate_to_agent",
            """{"agent_type":"forge","goal":"write tests"}""",
        )
        assertEquals("Agent: Forge", display.title)
        assertEquals("", display.summary)
    }

    @Test
    fun `delegate_to_agent with empty inputs renders bare title`() {
        val display = ToolDisplayName.resolve("delegate_to_agent", "")
        assertEquals("Agent: ", display.title)
        assertEquals("", display.summary)
    }

    @Test
    fun `spawn_sub_agent title is Worker, summary shows goal`() {
        val display = ToolDisplayName.resolve(
            "spawn_sub_agent",
            """{"goal":"fix bug"}""",
        )
        assertEquals("Worker", display.title)
        assertTrue(display.summary.contains("fix bug"))
    }

    @Test
    fun `unknown tool keeps raw tool name as title and shows summary`() {
        val display = ToolDisplayName.resolve(
            "Read",
            """{"file_path":"/x"}""",
        )
        assertEquals("Read", display.title)
        assertTrue(display.summary.contains("/x"))
    }
}
