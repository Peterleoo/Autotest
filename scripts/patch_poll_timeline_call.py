# -*- coding: utf-8 -*-
"""
Patch web/templates/index.html to:
1. Prioritize renderChatTimelineStream when session has timeline_blocks
2. Trigger touch ripple on tap/swipe logs in pollCurrentSession
"""

path = 'web/templates/index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                updateStopButtonState(data.status);
                renderChatStream(data);
                renderPipelineNodes(data.plan_steps, data.status, data.devices);
                renderConsoleTabs(data.devices);

                for (const [devId, devInfo] of Object.entries(data.devices || {})) {
                    if (!deviceLogsCache[devId]) deviceLogsCache[devId] = [];
                    if (devInfo.new_logs && devInfo.new_logs.length > 0) {
                        devInfo.new_logs.forEach(l => deviceLogsCache[devId].push(l));
                        deviceOffsets[devId] = devInfo.total_logs;
                    }
                }'''

replacement = '''                updateStopButtonState(data.status);
                if (data.timeline_blocks && data.timeline_blocks.length > 0) {
                    renderChatTimelineStream(data);
                } else {
                    renderChatStream(data);
                }
                renderPipelineNodes(data.plan_steps, data.status, data.devices);
                renderConsoleTabs(data.devices);

                for (const [devId, devInfo] of Object.entries(data.devices || {})) {
                    if (!deviceLogsCache[devId]) deviceLogsCache[devId] = [];
                    if (devInfo.new_logs && devInfo.new_logs.length > 0) {
                        devInfo.new_logs.forEach(l => {
                            deviceLogsCache[devId].push(l);
                            if (l.includes("tap") || l.includes("点击")) {
                                triggerScreenTouchRipple(0.5, 0.45, "原生手势轻触");
                            } else if (l.includes("swipe") || l.includes("滑动")) {
                                triggerScreenTouchRipple(0.5, 0.65, "屏幕滑动手势");
                            }
                        });
                        deviceOffsets[devId] = devInfo.total_logs;
                    }
                }'''

assert target in content, "Target not found in web/templates/index.html!"
content = content.replace(target, replacement, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully patched pollCurrentSession!")
