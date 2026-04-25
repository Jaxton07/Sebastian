package com.sebastian.android.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.sebastian.android.ui.navigation.Route
import com.sebastian.android.viewmodel.ProviderFormViewModel

private val PROVIDER_TYPE_OPTIONS = listOf("anthropic" to "Anthropic", "openai" to "OpenAI Compatible")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProviderFormPage(
    navController: NavController,
    providerId: String?,
    viewModel: ProviderFormViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    var apiKeyVisible by remember { mutableStateOf(false) }
    var serviceMenuExpanded by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        providerId?.let { viewModel.loadAccount(it) }
    }

    LaunchedEffect(uiState.isSaved) {
        if (uiState.isSaved) {
            val accountId = uiState.createdAccountId
            if (uiState.isNew && uiState.isCustomMode && accountId != null) {
                navController.navigate(Route.SettingsCustomModels(accountId)) {
                    popUpTo<Route.SettingsProviders> { inclusive = false }
                    launchSingleTop = true
                }
            } else {
                navController.popBackStack()
            }
        }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearError()
        }
    }

    val doneEnabled = uiState.isDirty && !uiState.isLoading

    Scaffold(
        topBar = {
            TopAppBar(
                title = {},
                navigationIcon = {
                    TextButton(onClick = { navController.popBackStack() }) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Text("返回", modifier = Modifier.padding(start = 4.dp))
                    }
                },
                actions = {
                    Surface(
                        onClick = { if (doneEnabled) viewModel.save(providerId) },
                        shape = RoundedCornerShape(18.dp),
                        color = if (doneEnabled) MaterialTheme.colorScheme.primary
                               else MaterialTheme.colorScheme.surfaceContainerHighest,
                        modifier = Modifier.padding(end = 8.dp),
                    ) {
                        Box(
                            contentAlignment = Alignment.Center,
                            modifier = Modifier
                                .height(36.dp)
                                .padding(horizontal = 16.dp),
                        ) {
                            if (uiState.isLoading) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(18.dp),
                                    strokeWidth = 2.dp,
                                    color = MaterialTheme.colorScheme.onSurface,
                                )
                            } else {
                                Text(
                                    "完成",
                                    fontSize = 15.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = if (doneEnabled) MaterialTheme.colorScheme.onPrimary
                                           else MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            if (providerId == null) {
                ServicePickerSection(
                    catalogProviders = uiState.catalogProviders,
                    selectedId = uiState.selectedCatalogId,
                    menuExpanded = serviceMenuExpanded,
                    onExpandedChange = { serviceMenuExpanded = it },
                    onSelect = viewModel::onCatalogSelect,
                )
            }

            AccountNameSection(
                name = uiState.name,
                onNameChange = viewModel::onNameChange,
            )

            if (uiState.isCustomMode) {
                CustomProviderSection(
                    providerType = uiState.providerType,
                    onProviderTypeChange = viewModel::onProviderTypeChange,
                    baseUrl = uiState.baseUrl,
                    onBaseUrlChange = viewModel::onBaseUrlChange,
                )
            }

            ApiKeySection(
                apiKey = uiState.apiKey,
                onApiKeyChange = viewModel::onApiKeyChange,
                apiKeyVisible = apiKeyVisible,
                onToggleVisibility = { apiKeyVisible = !apiKeyVisible },
                hasExistingApiKey = uiState.hasExistingApiKey,
                isEdit = providerId != null,
            )

            Spacer(Modifier.height(32.dp))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ServicePickerSection(
    catalogProviders: List<com.sebastian.android.data.model.CatalogProvider>,
    selectedId: String,
    menuExpanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
    onSelect: (String) -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            FieldLabel("服务")
            ExposedDropdownMenuBox(
                expanded = menuExpanded,
                onExpandedChange = onExpandedChange,
            ) {
                val selectedDisplay = if (selectedId == "custom") {
                    "自定义 (Custom)"
                } else {
                    catalogProviders.find { it.id == selectedId }?.displayName ?: "选择服务..."
                }
                OutlinedTextField(
                    value = selectedDisplay,
                    onValueChange = {},
                    readOnly = true,
                    singleLine = true,
                    shape = RoundedCornerShape(14.dp),
                    placeholder = { Text("选择服务...") },
                    trailingIcon = {
                        ExposedDropdownMenuDefaults.TrailingIcon(expanded = menuExpanded)
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .menuAnchor(type = MenuAnchorType.PrimaryNotEditable),
                )
                ExposedDropdownMenu(
                    expanded = menuExpanded,
                    onDismissRequest = { onExpandedChange(false) },
                ) {
                    catalogProviders.forEach { provider ->
                        DropdownMenuItem(
                            text = { Text(provider.displayName, fontWeight = FontWeight.Medium) },
                            onClick = {
                                onSelect(provider.id)
                                onExpandedChange(false)
                            },
                        )
                    }
                    DropdownMenuItem(
                        text = {
                            Text(
                                "自定义 (Custom)",
                                fontWeight = FontWeight.Medium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        },
                        onClick = {
                            onSelect("custom")
                            onExpandedChange(false)
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun AccountNameSection(
    name: String,
    onNameChange: (String) -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            FieldLabel("名称")
            OutlinedTextField(
                value = name,
                onValueChange = onNameChange,
                placeholder = { Text("我的 Claude / OpenAI / DeepSeek...") },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun CustomProviderSection(
    providerType: String,
    onProviderTypeChange: (String) -> Unit,
    baseUrl: String,
    onBaseUrlChange: (String) -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            FieldLabel("Provider 类型")
            SegmentedControl(
                options = PROVIDER_TYPE_OPTIONS.map { it.first },
                labels = PROVIDER_TYPE_OPTIONS.map { it.second },
                selected = providerType,
                onSelect = onProviderTypeChange,
            )

            FieldLabel("Base URL", topPadding = 14.dp)
            OutlinedTextField(
                value = baseUrl,
                onValueChange = onBaseUrlChange,
                placeholder = { Text("https://api.example.com/v1") },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun ApiKeySection(
    apiKey: String,
    onApiKeyChange: (String) -> Unit,
    apiKeyVisible: Boolean,
    onToggleVisibility: () -> Unit,
    hasExistingApiKey: Boolean,
    isEdit: Boolean,
) {
    Surface(
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            FieldLabel("API Key")
            OutlinedTextField(
                value = apiKey,
                onValueChange = onApiKeyChange,
                placeholder = {
                    if (isEdit && hasExistingApiKey) {
                        Text("••••••••")
                    } else {
                        Text("sk-...")
                    }
                },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                visualTransformation = if (apiKeyVisible) VisualTransformation.None
                                      else PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                trailingIcon = {
                    IconButton(onClick = onToggleVisibility) {
                        Text(
                            if (apiKeyVisible) "隐藏" else "显示",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
            if (isEdit && hasExistingApiKey) {
                Text(
                    "留空则保持原有 Key 不变",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }
    }
}

@Composable
private fun FieldLabel(text: String, topPadding: androidx.compose.ui.unit.Dp = 0.dp) {
    Text(
        text,
        fontSize = 13.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = topPadding, bottom = 8.dp),
    )
}

@Composable
private fun SegmentedControl(
    options: List<String>,
    labels: List<String>,
    selected: String,
    onSelect: (String) -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surfaceContainerHighest,
    ) {
        Row(modifier = Modifier.padding(4.dp)) {
            options.forEachIndexed { index, option ->
                val active = option == selected
                Surface(
                    onClick = { onSelect(option) },
                    shape = RoundedCornerShape(12.dp),
                    color = if (active) MaterialTheme.colorScheme.surface else Color.Transparent,
                    modifier = Modifier
                        .weight(1f)
                        .height(40.dp),
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text(
                            labels.getOrElse(index) { option },
                            fontSize = 15.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = if (active) MaterialTheme.colorScheme.onSurface
                                   else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}
