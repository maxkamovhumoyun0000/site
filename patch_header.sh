#!/bin/bash
sed -i '/fun MainScreen(/i \
@Composable fun TopScreenHeader(title: String, onBack: () -> Unit) {\
    Box(modifier = Modifier.fillMaxWidth().background(Navy900).statusBarsPadding().padding(horizontal = 8.dp, vertical = 12.dp)) {\
        Row(verticalAlignment = Alignment.CenterVertically) {\
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, null, tint = Color.White) }\
            Text(title, color = Color.White, fontWeight = FontWeight.Black, fontSize = 18.sp, modifier = Modifier.padding(start = 8.dp))\
        }\
    }\
}\
' /home/xumoyun-maxkamov/AndroidStudioProjects/DiamondEducationStudentPlatform/app/src/main/java/com/diamond/education/student/platform/MainActivity.kt
