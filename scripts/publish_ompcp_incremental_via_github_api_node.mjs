#!/usr/bin/env node
import { promises as fs } from "node:fs";
import path from "node:path";

function parseArgs(argv) {
  const args = {
    sourcePath: "C:\\codex-data\\OMPCP",
    owner: "dongfanghong656",
    repo: "OMPCP",
    branch: "main",
    commitMessage: "Update OMPCP files",
    tokenEnvName: "GITHUB_TOKEN",
    paths: [],
  };
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
      case "--path":
        args.paths.push(next());
        break;
      default:
        throw new Error(`Unknown argument: ${key}`);
    }
  }
  if (args.paths.length === 0) {
    throw new Error("At least one --path is required.");
  }
  return args;
}

async function githubRequest({ method, url, token, body }) {
  const headers = {
    "Authorization": `Bearer ${token}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "OMPCP-Codex-Incremental-Publisher",
  };
  const init = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let response;
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    try {
      response = await fetch(url, init);
      break;
    } catch (error) {
      if (attempt === 5) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 500 * attempt));
    }
  }
  if (!response) {
    throw new Error(`GitHub API request failed before response: ${method} ${url}`);
  }
  const text = await response.text();
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

function normalizeRepoPath(value) {
  return value.replaceAll("\\", "/").replace(/^\/+/, "");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const token = process.env[args.tokenEnvName] || process.env.GH_TOKEN;
  if (!token) {
    throw new Error(`Missing GitHub token. Set ${args.tokenEnvName} or GH_TOKEN in the process environment.`);
  }
  const source = path.resolve(args.sourcePath);
  const apiBase = `https://api.github.com/repos/${args.owner}/${args.repo}`;
  const request = (method, url, body) => githubRequest({ method, url, token, body });

  const ref = await request("GET", `${apiBase}/git/ref/heads/${args.branch}`);
  const parentSha = ref.object.sha;
  const parentCommit = await request("GET", `${apiBase}/git/commits/${parentSha}`);
  const baseTreeSha = parentCommit.tree.sha;

  console.log(`incremental_source=${source}`);
  console.log(`remote_parent=${parentSha}`);
  console.log(`changed_file_count=${args.paths.length}`);

  const treeEntries = [];
  for (const rawPath of args.paths) {
    const repoPath = normalizeRepoPath(rawPath);
    const fullPath = path.join(source, repoPath);
    const bytes = await fs.readFile(fullPath);
    const blob = await request("POST", `${apiBase}/git/blobs`, {
      content: bytes.toString("base64"),
      encoding: "base64",
    });
    treeEntries.push({
      path: repoPath,
      mode: "100644",
      type: "blob",
      sha: blob.sha,
    });
    console.log(`updated_blob=${repoPath}`);
  }

  const tree = await request("POST", `${apiBase}/git/trees`, {
    base_tree: baseTreeSha,
    tree: treeEntries,
  });
  const commit = await request("POST", `${apiBase}/git/commits`, {
    message: args.commitMessage,
    tree: tree.sha,
    parents: [parentSha],
  });
  await request("PATCH", `${apiBase}/git/refs/heads/${args.branch}`, {
    sha: commit.sha,
    force: false,
  });
  console.log(`commit_sha=${commit.sha}`);
  console.log(`published=https://github.com/${args.owner}/${args.repo}/tree/${args.branch}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
