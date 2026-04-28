#!/usr/bin/env node
import { promises as fs } from "node:fs";
import path from "node:path";

const DEFAULTS = {
  sourcePath: "C:\\codex-data\\OMPCP",
  owner: "dongfanghong656",
  repo: "OMPCP",
  branch: "main",
  commitMessage: "Initialize OMPCP OCT Mie PSF diagnostic stack",
  tokenEnvName: "GITHUB_TOKEN",
  allowReplaceRemoteTree: false,
  dryRun: false,
};

function parseArgs(argv) {
  const args = { ...DEFAULTS };
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) {
        throw new Error(`Missing value after ${key}`);
      }
      i += 1;
      return argv[i];
    };
    switch (key) {
      case "--source-path":
        args.sourcePath = next();
        break;
      case "--owner":
        args.owner = next();
        break;
      case "--repo":
        args.repo = next();
        break;
      case "--branch":
        args.branch = next();
        break;
      case "--commit-message":
        args.commitMessage = next();
        break;
      case "--token-env-name":
        args.tokenEnvName = next();
        break;
      case "--allow-replace-remote-tree":
        args.allowReplaceRemoteTree = true;
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--help":
        console.log(`Usage: node publish_ompcp_via_github_api_node.mjs [options]

Options:
  --source-path PATH
  --owner OWNER
  --repo REPO
  --branch BRANCH
  --commit-message MESSAGE
  --token-env-name NAME
  --allow-replace-remote-tree
  --dry-run`);
        process.exit(0);
        break;
      default:
        throw new Error(`Unknown argument: ${key}`);
    }
  }
  return args;
}

function getToken(name) {
  const token = process.env[name] || process.env.GH_TOKEN;
  if (!token) {
    throw new Error(`Missing GitHub token. Set ${name} or GH_TOKEN in the process environment. Do not write tokens into files.`);
  }
  return token;
}

function isExcluded(relativePath) {
  const normalized = relativePath.replaceAll("\\", "/");
  return (
    normalized.startsWith(".git/") ||
    normalized === ".git" ||
    normalized.startsWith("__pycache__/") ||
    normalized.includes("/__pycache__/") ||
    normalized.startsWith(".pytest_cache/") ||
    normalized.includes("/.pytest_cache/") ||
    normalized.startsWith("reports/_unit_test_tmp/") ||
    normalized.startsWith("reports/actions_run_") ||
    /^reports\/[^/]*_unit_test_tmp[^/]*\//.test(normalized) ||
    normalized.endsWith(".pyc")
  );
}

async function walkFiles(root, current = root, out = []) {
  const entries = await fs.readdir(current, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(current, entry.name);
    const relative = path.relative(root, full).replaceAll("\\", "/");
    if (isExcluded(relative)) {
      continue;
    }
    if (entry.isDirectory()) {
      await walkFiles(root, full, out);
    } else if (entry.isFile()) {
      const stat = await fs.stat(full);
      out.push({ fullName: full, path: relative, length: stat.size });
    }
  }
  return out;
}

async function githubRequest({ method, url, token, body, allowNotFound = false }) {
  const headers = {
    "Authorization": `Bearer ${token}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "OMPCP-Codex-Publisher",
  };
  const init = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let response;
  let lastNetworkError;
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    try {
      response = await fetch(url, init);
      break;
    } catch (error) {
      lastNetworkError = error;
      if (attempt === 5) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 500 * attempt));
    }
  }
  if (!response) {
    throw lastNetworkError || new Error(`GitHub API request failed before response: ${method} ${url}`);
  }
  const text = await response.text();
  if (allowNotFound && (response.status === 404 || response.status === 409)) {
    return null;
  }
  if (!response.ok) {
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      detail = parsed.message ? `${parsed.message}\n${JSON.stringify(parsed, null, 2)}` : JSON.stringify(parsed, null, 2);
    } catch {
      // Keep raw text.
    }
    throw new Error(`GitHub API request failed: ${method} ${url}\n${detail}`);
  }
  return text ? JSON.parse(text) : {};
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const source = path.resolve(args.sourcePath);
  const files = (await walkFiles(source)).sort((a, b) => a.path.localeCompare(b.path));
  const totalBytes = files.reduce((sum, file) => sum + file.length, 0);

  console.log(`publish_source=${source}`);
  console.log(`publish_file_count=${files.length}`);
  console.log(`publish_total_mb=${Math.round((totalBytes / 1024 / 1024) * 100) / 100}`);

  if (args.dryRun) {
    for (const file of files.slice(0, 20)) {
      console.log(`${file.path}\t${file.length}`);
    }
    if (files.length > 20) {
      console.log(`... ${files.length - 20} more files`);
    }
    return;
  }

  const token = getToken(args.tokenEnvName);
  const apiBase = `https://api.github.com/repos/${args.owner}/${args.repo}`;
  const request = (method, url, body, options = {}) => githubRequest({
    method,
    url,
    token,
    body,
    ...options,
  });

  const repoInfo = await request("GET", apiBase);
  console.log(`target_repo=${repoInfo.full_name}`);

  const refReadUri = `${apiBase}/git/ref/heads/${args.branch}`;
  const refWriteUri = `${apiBase}/git/refs/heads/${args.branch}`;
  let ref = await request("GET", refReadUri, undefined, { allowNotFound: true });
  let parentSha = null;
  if (ref) {
    parentSha = ref.object.sha;
    if (!args.allowReplaceRemoteTree) {
      throw new Error(`Remote branch '${args.branch}' already exists at ${parentSha}. Re-run with --allow-replace-remote-tree if replacing its tree is intended.`);
    }
    console.log(`remote_parent=${parentSha}`);
  } else {
    console.log("remote_parent=<none>");
    const bootstrap = await request("PUT", `${apiBase}/contents/.ompcp_bootstrap`, {
      message: "Bootstrap empty OMPCP repository",
      content: Buffer.from("bootstrap\n", "utf8").toString("base64"),
      branch: args.branch,
    });
    parentSha = bootstrap.commit.sha;
    ref = { object: { sha: parentSha } };
    console.log(`bootstrap_parent=${parentSha}`);
  }

  const treeEntries = [];
  for (let index = 0; index < files.length; index += 1) {
    const file = files[index];
    if ((index + 1) % 50 === 0) {
      console.log(`uploaded_blobs=${index + 1}/${files.length}`);
    }
    const bytes = await fs.readFile(file.fullName);
    const blob = await request("POST", `${apiBase}/git/blobs`, {
      content: bytes.toString("base64"),
      encoding: "base64",
    });
    treeEntries.push({
      path: file.path,
      mode: "100644",
      type: "blob",
      sha: blob.sha,
    });
  }

  const tree = await request("POST", `${apiBase}/git/trees`, { tree: treeEntries });
  console.log(`tree_sha=${tree.sha}`);

  const commitBody = {
    message: args.commitMessage,
    tree: tree.sha,
  };
  if (parentSha) {
    commitBody.parents = [parentSha];
  }
  const commit = await request("POST", `${apiBase}/git/commits`, commitBody);
  console.log(`commit_sha=${commit.sha}`);

  if (ref) {
    await request("PATCH", refWriteUri, { sha: commit.sha, force: false });
  } else {
    await request("POST", `${apiBase}/git/refs`, {
      ref: `refs/heads/${args.branch}`,
      sha: commit.sha,
    });
  }

  console.log(`published=https://github.com/${args.owner}/${args.repo}/tree/${args.branch}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
