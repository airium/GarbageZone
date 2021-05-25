# 清理 Windows Explorer Quick Access

Quick Access 设定保存于该文件：\
`%AppData%\Microsoft\Windows\Recent\AutomaticDestinations\f01b4d95cf55d32a.automaticDestinations-ms`\
删除该文件将使得 Quick Access 被重置，可以解决一些无法 pin/unpin 的问题。

Quick Access 被重置时将默认添加以下 4 个文件夹：

1. `%USERPROFILE\Desktop`
2. `%USERPROFILE\Documents`
3. `%USERPROFILE\Downloads`
4. `%USERPROFILE\Pictures`

同时将读取 `%USERPROFILE%\Links` 下的所有快捷方式。

可以定期备份 Quick Access 所有路径的快捷方式。这样在重置 Quick Access 或配置新机器时可以快速恢复先前设定。
