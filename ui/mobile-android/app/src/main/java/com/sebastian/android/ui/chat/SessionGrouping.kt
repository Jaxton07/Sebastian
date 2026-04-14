package com.sebastian.android.ui.chat

import com.sebastian.android.data.model.Session
import java.time.LocalDate
import java.time.format.DateTimeParseException

sealed class SessionBucket {
    abstract val key: String
    abstract val label: String
    abstract val sessions: List<Session>

    data class Recent(
        override val key: String,
        override val label: String,
        override val sessions: List<Session>,
    ) : SessionBucket()

    data class Month(
        val year: Int,
        val month: Int,
        override val sessions: List<Session>,
    ) : SessionBucket() {
        override val key: String = "m-$year-$month"
        override val label: String = "${year}年${month}月"
    }

    data class Year(
        val year: Int,
        val months: List<Month>,
    ) : SessionBucket() {
        override val key: String = "y-$year"
        override val label: String = "${year}年"
        override val sessions: List<Session>
            get() = months.flatMap { it.sessions }
    }
}

data class GroupedSessions(
    val recent: List<SessionBucket.Recent>,
    val years: List<SessionBucket.Year>,
)

private fun parseDate(raw: String?): LocalDate? {
    if (raw == null || raw.length < 10) return null
    return try {
        LocalDate.parse(raw.substring(0, 10))
    } catch (_: DateTimeParseException) {
        null
    }
}

/** ISO 字符串字典序 == 时间序；null 排最后。desc。 */
private val sessionTimeDesc = Comparator<Session> { a, b ->
    val av = a.lastActivityAt
    val bv = b.lastActivityAt
    when {
        av == null && bv == null -> 0
        av == null -> 1
        bv == null -> -1
        else -> bv.compareTo(av)
    }
}

fun groupSessions(
    sessions: List<Session>,
    now: LocalDate = LocalDate.now(),
): GroupedSessions {
    val today = mutableListOf<Session>()
    val yesterday = mutableListOf<Session>()
    val within7 = mutableListOf<Session>()
    val within30 = mutableListOf<Session>()
    val monthMap = linkedMapOf<Pair<Int, Int>, MutableList<Session>>()

    for (session in sessions) {
        val date = parseDate(session.lastActivityAt)
        if (date == null) {
            today += session
            continue
        }
        val daysAgo = java.time.temporal.ChronoUnit.DAYS.between(date, now)
        when {
            daysAgo <= 0L -> today += session
            daysAgo == 1L -> yesterday += session
            daysAgo in 2L..7L -> within7 += session
            daysAgo in 8L..30L -> within30 += session
            else -> {
                val key = date.year to date.monthValue
                monthMap.getOrPut(key) { mutableListOf() } += session
            }
        }
    }

    val recent = buildList {
        if (today.isNotEmpty()) {
            add(SessionBucket.Recent("today", "今天", today.sortedWith(sessionTimeDesc)))
        }
        if (yesterday.isNotEmpty()) {
            add(SessionBucket.Recent("yesterday", "昨天", yesterday.sortedWith(sessionTimeDesc)))
        }
        if (within7.isNotEmpty()) {
            add(SessionBucket.Recent("within7", "7天内", within7.sortedWith(sessionTimeDesc)))
        }
        if (within30.isNotEmpty()) {
            add(SessionBucket.Recent("within30", "30天内", within30.sortedWith(sessionTimeDesc)))
        }
    }

    val byYear = monthMap.entries
        .groupBy { it.key.first }
        .toSortedMap(compareByDescending { it })
    val years = byYear.map { (year, entries) ->
        val months = entries
            .sortedByDescending { it.key.second }
            .map { (yk, list) ->
                SessionBucket.Month(
                    year = yk.first,
                    month = yk.second,
                    sessions = list.sortedWith(sessionTimeDesc),
                )
            }
        SessionBucket.Year(year = year, months = months)
    }

    return GroupedSessions(recent = recent, years = years)
}

fun defaultExpanded(
    grouped: GroupedSessions,
    now: LocalDate = LocalDate.now(),
): Map<String, Boolean> {
    val map = linkedMapOf<String, Boolean>()
    grouped.recent.forEach { map[it.key] = true }
    grouped.years.forEach { year ->
        map[year.key] = (year.year == now.year)
        year.months.forEach { map[it.key] = false }
    }
    return map
}
