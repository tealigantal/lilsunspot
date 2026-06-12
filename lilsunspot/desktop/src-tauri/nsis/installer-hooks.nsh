!macro LILSUNSPOT_RECREATE_SHORTCUT shortcutPath
  !define UniqueID ${__LINE__}
  IfFileExists "${shortcutPath}" 0 done_${UniqueID}
    Delete "${shortcutPath}"
    CreateShortcut "${shortcutPath}" "$INSTDIR\${MAINBINARYNAME}.exe" "" "$INSTDIR\${MAINBINARYNAME}.exe" 0
    !insertmacro SetLnkAppUserModelId "${shortcutPath}"
  done_${UniqueID}:
  !undef UniqueID
!macroend

!macro LILSUNSPOT_STOP_SIDECAR executableName
  !if "${INSTALLMODE}" == "currentUser"
    nsis_tauri_utils::FindProcessCurrentUser "${executableName}"
  !else
    nsis_tauri_utils::FindProcess "${executableName}"
  !endif
  Pop $R0
  ${If} $R0 = 0
    DetailPrint "正在关闭旧版小黑子本地服务：${executableName}"
    !if "${INSTALLMODE}" == "currentUser"
      nsis_tauri_utils::KillProcessCurrentUser "${executableName}"
    !else
      nsis_tauri_utils::KillProcess "${executableName}"
    !endif
    Pop $R0
    Sleep 800
    ${If} $R0 != 0
    ${AndIf} $R0 != 2
      Abort "无法关闭旧版小黑子本地服务。请先退出小黑子，再重新运行安装包。"
    ${EndIf}
  ${EndIf}
!macroend

!macro LILSUNSPOT_STOP_OLD_MAIN executableName
  !if "${INSTALLMODE}" == "currentUser"
    nsis_tauri_utils::FindProcessCurrentUser "${executableName}"
  !else
    nsis_tauri_utils::FindProcess "${executableName}"
  !endif
  Pop $R0
  ${If} $R0 = 0
    DetailPrint "正在关闭旧版小黑子桌面程序：${executableName}"
    !if "${INSTALLMODE}" == "currentUser"
      nsis_tauri_utils::KillProcessCurrentUser "${executableName}"
    !else
      nsis_tauri_utils::KillProcess "${executableName}"
    !endif
    Pop $R0
    Sleep 800
    ${If} $R0 != 0
    ${AndIf} $R0 != 2
      Abort "无法关闭旧版小黑子桌面程序。请先退出小黑子，再重新运行安装包。"
    ${EndIf}
  ${EndIf}
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro LILSUNSPOT_STOP_OLD_MAIN "lilsunspot_desktop.exe"
  !insertmacro LILSUNSPOT_STOP_SIDECAR "lilsunspotd.exe"
  !insertmacro LILSUNSPOT_STOP_SIDECAR "lilsunspotd-x86_64-pc-windows-msvc.exe"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro LILSUNSPOT_STOP_OLD_MAIN "lilsunspot_desktop.exe"
  !insertmacro LILSUNSPOT_STOP_SIDECAR "lilsunspotd.exe"
  !insertmacro LILSUNSPOT_STOP_SIDECAR "lilsunspotd-x86_64-pc-windows-msvc.exe"
!macroend

!macro NSIS_HOOK_POSTINSTALL
  Delete "$INSTDIR\lilsunspot_desktop.exe"
  Delete "$INSTDIR\lilsunspotd.exe"
  Delete "$INSTDIR\lilsunspotd-x86_64-pc-windows-msvc.exe"
  !insertmacro LILSUNSPOT_RECREATE_SHORTCUT "$DESKTOP\${PRODUCTNAME}.lnk"
  !if "${STARTMENUFOLDER}" != ""
    !insertmacro LILSUNSPOT_RECREATE_SHORTCUT "$SMPROGRAMS\$AppStartMenuFolder\${PRODUCTNAME}.lnk"
  !else
    !insertmacro LILSUNSPOT_RECREATE_SHORTCUT "$SMPROGRAMS\${PRODUCTNAME}.lnk"
  !endif
!macroend
