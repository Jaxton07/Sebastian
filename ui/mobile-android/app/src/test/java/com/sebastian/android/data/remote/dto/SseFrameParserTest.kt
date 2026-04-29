package com.sebastian.android.data.remote.dto

import com.sebastian.android.data.model.StreamEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class SseFrameParserTest {

    @Test
    fun `tool_executed without artifact parses correctly with null artifact`() {
        val raw = """{"type":"tool.executed","data":{"session_id":"s1","tool_id":"t1","name":"read_file","result_summary":"ok"}}"""
        val event = SseFrameParser.parse(raw) as StreamEvent.ToolExecuted
        assertEquals("s1", event.sessionId)
        assertEquals("t1", event.toolId)
        assertEquals("read_file", event.name)
        assertEquals("ok", event.resultSummary)
        assertNull(event.artifact)
    }

    @Test
    fun `tool_executed with image artifact parses artifact fields`() {
        val raw = """
            {
              "type": "tool.executed",
              "data": {
                "session_id": "s1",
                "tool_id": "t2",
                "name": "send_file",
                "result_summary": "sent",
                "artifact": {
                  "kind": "image",
                  "attachment_id": "att-99",
                  "filename": "photo.jpg",
                  "mime_type": "image/jpeg",
                  "size_bytes": 4096,
                  "download_url": "/api/v1/attachments/att-99",
                  "thumbnail_url": "/api/v1/attachments/att-99/thumbnail"
                }
              }
            }
        """.trimIndent()
        val event = SseFrameParser.parse(raw) as StreamEvent.ToolExecuted
        assertEquals("send_file", event.name)
        val artifact = event.artifact
        assertNotNull(artifact)
        assertEquals("image", artifact!!.kind)
        assertEquals("att-99", artifact.attachmentId)
        assertEquals("photo.jpg", artifact.filename)
        assertEquals("image/jpeg", artifact.mimeType)
        assertEquals(4096L, artifact.sizeBytes)
        assertEquals("/api/v1/attachments/att-99", artifact.downloadUrl)
        assertEquals("/api/v1/attachments/att-99/thumbnail", artifact.thumbnailUrl)
        assertNull(artifact.textExcerpt)
    }

    @Test
    fun `tool_executed with text_file artifact parses artifact fields`() {
        val raw = """
            {
              "type": "tool.executed",
              "data": {
                "session_id": "s1",
                "tool_id": "t3",
                "name": "send_file",
                "result_summary": "sent",
                "artifact": {
                  "kind": "text_file",
                  "attachment_id": "att-42",
                  "filename": "report.txt",
                  "mime_type": "text/plain",
                  "size_bytes": 256,
                  "download_url": "/api/v1/attachments/att-42",
                  "text_excerpt": "first 200 chars..."
                }
              }
            }
        """.trimIndent()
        val event = SseFrameParser.parse(raw) as StreamEvent.ToolExecuted
        val artifact = event.artifact
        assertNotNull(artifact)
        assertEquals("text_file", artifact!!.kind)
        assertEquals("att-42", artifact.attachmentId)
        assertEquals("report.txt", artifact.filename)
        assertEquals(256L, artifact.sizeBytes)
        assertEquals("/api/v1/attachments/att-42", artifact.downloadUrl)
        assertNull(artifact.thumbnailUrl)
        assertEquals("first 200 chars...", artifact.textExcerpt)
    }

    @Test
    fun `tool_executed with artifact missing attachment_id returns null artifact`() {
        val raw = """
            {
              "type": "tool.executed",
              "data": {
                "session_id": "s1",
                "tool_id": "t4",
                "name": "send_file",
                "result_summary": "",
                "artifact": {
                  "kind": "image"
                }
              }
            }
        """.trimIndent()
        val event = SseFrameParser.parse(raw) as StreamEvent.ToolExecuted
        assertNull(event.artifact)
    }
}
