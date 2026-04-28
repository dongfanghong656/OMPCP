# Push to GitHub

Remote repository:

```text
https://github.com/dongfanghong656/OMPCP
```

## Recommended path on a normal Git-enabled machine

```powershell
cd C:\codex-data\OMPCP
git init
git branch -M main
git remote add origin https://github.com/dongfanghong656/OMPCP.git
git add .
git commit -m "Initialize OMPCP OCT Mie PSF diagnostic stack"
git push -u origin main
```

If the remote repository already contains files, use this safer route:

```powershell
git fetch origin
git pull --rebase origin main
git push -u origin main
```

## Current local environment note

In this Codex workspace, `git init` cannot complete in freshly created directories because the filesystem allows creating `.git/config.lock` but denies the lock-file rename/delete operation that Git needs. The clean publish archive is therefore provided as a fallback for GitHub web upload or for pushing from a normal local Git environment.

Clean publish archive generated in this workspace:

```text
C:\codex-data\OMPCP_publish_clean_20260427-224209.zip
```

## Sandbox workaround already prepared

This workspace can reach `ssh.github.com:443`, even though `github.com:443` times out. A pushable repository was therefore generated without `git init`, using direct Git object creation:

```text
C:\codex-data\OMPCP_pushable_latest
```

The push remote uses SSH over port 443:

```text
ssh://git@ssh.github.com:443/dongfanghong656/OMPCP.git
```

Add this deploy key or account SSH key to GitHub first:

```text
C:\codex-data\OMPCP_github_deploy_public_key.txt
```

Then push with:

```powershell
powershell -ExecutionPolicy Bypass -File C:\codex-data\OMPCP\scripts\push_ompcp_ssh443.ps1 `
  -RepoPath C:\codex-data\OMPCP_pushable_latest
```

If the key is not added to GitHub, the expected failure is:

```text
git@ssh.github.com: Permission denied (publickey).
```

## Token-based API publishing

If Git HTTPS is blocked and SSH keys are not configured, use the GitHub API publisher. It reads the token only from an environment variable and never writes it into files.

First set the token in the current PowerShell session:

```powershell
$env:GITHUB_TOKEN = '<paste token here>'
```

Preview the publish set:

```powershell
powershell -ExecutionPolicy Bypass -File C:\codex-data\OMPCP\scripts\publish_ompcp_via_github_api.ps1 `
  -SourcePath C:\codex-data\OMPCP `
  -DryRun
```

Publish to a new or empty `main` branch:

```powershell
powershell -ExecutionPolicy Bypass -File C:\codex-data\OMPCP\scripts\publish_ompcp_via_github_api.ps1 `
  -SourcePath C:\codex-data\OMPCP
```

If the remote `main` branch already exists and replacing its tree is intended, add:

```powershell
-AllowReplaceRemoteTree
```

After publishing, clear the process token:

```powershell
Remove-Item Env:GITHUB_TOKEN
```

## Safer token handoff for Codex-driven publishing

If Codex needs to publish without seeing or logging the token in commands, save the token once through a hidden PowerShell prompt:

```powershell
powershell -ExecutionPolicy Bypass -File C:\codex-data\OMPCP\scripts\save_github_token_secure.ps1
```

This stores an encrypted Windows DPAPI SecureString outside the repository:

```text
C:\codex-data\OMPCP_secrets\github_token.clixml
```

After that, Codex can publish by running:

```powershell
powershell -ExecutionPolicy Bypass -File C:\codex-data\OMPCP\scripts\publish_ompcp_from_secure_token.ps1 -SourcePath C:\codex-data\OMPCP
```

If `main` already exists and replacing its tree is intended:

```powershell
powershell -ExecutionPolicy Bypass -File C:\codex-data\OMPCP\scripts\publish_ompcp_from_secure_token.ps1 -SourcePath C:\codex-data\OMPCP -AllowReplaceRemoteTree
```

This route keeps the token out of command history, repository files, Git remotes, and GitHub Actions logs. The encrypted secret can only be decrypted by the same Windows user profile that saved it.
