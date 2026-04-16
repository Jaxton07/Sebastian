package com.sebastian.android.ui.settings.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.sebastian.android.data.model.Provider

@Composable
fun ProviderPickerDialog(
    currentProviderId: String?,
    providers: List<Provider>,
    onDismiss: () -> Unit,
    onSelect: (String?) -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Select LLM Provider") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 480.dp)
                    .verticalScroll(rememberScrollState()),
            ) {
                ListItem(
                    headlineContent = { Text("Use default provider") },
                    trailingContent = if (currentProviderId == null) {
                        { Icon(Icons.Filled.CheckCircle, contentDescription = "selected") }
                    } else null,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onSelect(null) },
                )
                HorizontalDivider()
                providers.forEach { provider ->
                    ListItem(
                        headlineContent = { Text(provider.name) },
                        supportingContent = { Text(provider.type) },
                        trailingContent = if (currentProviderId == provider.id) {
                            { Icon(Icons.Filled.CheckCircle, contentDescription = "selected") }
                        } else null,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onSelect(provider.id) },
                    )
                    HorizontalDivider()
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Close") }
        },
    )
}
