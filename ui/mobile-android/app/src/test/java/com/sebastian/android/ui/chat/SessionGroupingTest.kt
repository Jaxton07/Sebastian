package com.sebastian.android.ui.chat

import com.sebastian.android.data.model.Session
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class SessionGroupingTest {

    private val now: LocalDate = LocalDate.of(2026, 4, 14)

    private fun s(id: String, date: String?): Session =
        Session(id = id, title = id, agentType = "chat", lastActivityAt = date)

    @Test
    fun `today bucket covers now`() {
        val grouped = groupSessions(listOf(s("a", "2026-04-14T10:00:00")), now)
        assertEquals(1, grouped.recent.size)
        assertEquals("today", grouped.recent[0].key)
        assertEquals(listOf("a"), grouped.recent[0].sessions.map { it.id })
    }

    @Test
    fun `yesterday bucket covers now minus 1`() {
        val grouped = groupSessions(listOf(s("a", "2026-04-13T23:59:00")), now)
        assertEquals("yesterday", grouped.recent[0].key)
    }

    @Test
    fun `within7 covers 2 to 7 days ago exclusive of yesterday`() {
        val grouped = groupSessions(
            listOf(s("a", "2026-04-12T00:00:00"), s("b", "2026-04-07T00:00:00")),
            now,
        )
        assertEquals(1, grouped.recent.size)
        assertEquals("within7", grouped.recent[0].key)
        assertEquals(listOf("a", "b"), grouped.recent[0].sessions.map { it.id })
    }

    @Test
    fun `within30 covers 8 to 30 days ago`() {
        val grouped = groupSessions(
            listOf(s("a", "2026-04-06T00:00:00"), s("b", "2026-03-15T00:00:00")),
            now,
        )
        assertEquals("within30", grouped.recent[0].key)
        assertEquals(listOf("a", "b"), grouped.recent[0].sessions.map { it.id })
    }

    @Test
    fun `older than 30 days goes into year and month`() {
        val grouped = groupSessions(
            listOf(s("a", "2026-03-10T00:00:00"), s("b", "2025-12-31T23:59:00")),
            now,
        )
        assertTrue(grouped.recent.isEmpty())
        assertEquals(2, grouped.years.size)
        assertEquals(2026, grouped.years[0].year)
        assertEquals(2025, grouped.years[1].year)
        assertEquals(3, grouped.years[0].months[0].month)
        assertEquals(12, grouped.years[1].months[0].month)
    }

    @Test
    fun `null lastActivityAt falls back to today`() {
        val grouped = groupSessions(listOf(s("a", null)), now)
        assertEquals("today", grouped.recent[0].key)
    }

    @Test
    fun `within-bucket sort is lastActivityAt desc with second precision`() {
        val grouped = groupSessions(
            listOf(
                s("early", "2026-04-14T08:00:30"),
                s("late", "2026-04-14T08:00:45"),
                s("mid", "2026-04-14T08:00:40"),
            ),
            now,
        )
        assertEquals(listOf("late", "mid", "early"), grouped.recent[0].sessions.map { it.id })
    }

    @Test
    fun `months within a year are desc`() {
        val grouped = groupSessions(
            listOf(
                s("a", "2026-02-01T00:00:00"),
                s("b", "2026-03-01T00:00:00"),
                s("c", "2026-01-01T00:00:00"),
            ),
            now,
        )
        val months = grouped.years[0].months.map { it.month }
        assertEquals(listOf(3, 2, 1), months)
    }

    @Test
    fun `empty input produces empty grouped`() {
        val grouped = groupSessions(emptyList(), now)
        assertTrue(grouped.recent.isEmpty())
        assertTrue(grouped.years.isEmpty())
    }

    @Test
    fun `recent bucket order is today yesterday within7 within30`() {
        val grouped = groupSessions(
            listOf(
                s("w30", "2026-03-20T00:00:00"),
                s("today", "2026-04-14T00:00:00"),
                s("w7", "2026-04-10T00:00:00"),
                s("y", "2026-04-13T00:00:00"),
            ),
            now,
        )
        assertEquals(listOf("today", "yesterday", "within7", "within30"), grouped.recent.map { it.key })
    }

    @Test
    fun `defaultExpanded expands recent and current year only`() {
        val grouped = groupSessions(
            listOf(
                s("now", "2026-04-14T00:00:00"),
                s("cur-year", "2026-02-01T00:00:00"),
                s("old", "2025-06-01T00:00:00"),
            ),
            now,
        )
        val defaults = defaultExpanded(grouped, now)
        assertEquals(true, defaults["today"])
        assertEquals(true, defaults["y-2026"])
        assertEquals(false, defaults["y-2025"])
        assertEquals(false, defaults["m-2026-2"])
        assertEquals(false, defaults["m-2025-6"])
    }
}
