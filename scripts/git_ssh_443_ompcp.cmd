@echo off
C:\Windows\System32\OpenSSH\ssh.exe -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=C:\codex-data\OMPCP_github_known_hosts -i C:\codex-data\OMPCP_github_deploy_ed25519 %*
