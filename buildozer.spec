[app]
title = Tracker
package.name = tracker
package.domain = org.lifetracker
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3,kivy==2.3.0,plyer,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = POST_NOTIFICATIONS,VIBRATE
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
