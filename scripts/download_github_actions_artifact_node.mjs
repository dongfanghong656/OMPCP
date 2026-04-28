#!/usr/bin/env node
import { promises as fs } from "node:fs";
import path from "node:path";

function parseArgs(argv) {
  const args = {
    owner: "dongfanghong656",
    repo: "OMPCP",
    artifactId: null,
    outputPath: null,
    tokenEnvName: "GITHUB_TOKEN",
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
      case "--owner":
        args.owner = next();
        break;
      case "--repo":
        args.repo = next();
        break;
      case "--artifact-id":
        args.artifactId = next();
        break;
      case "--output-path":
        args.outputPath = next();
        break;
      case "--token-env-name":
        args.tokenEnvName = next();
        break;
      default:
        throw new Error(`Unknown argument: ${key}`);
    }
  }
  if (!args.artifactId) {
    throw new Error("--artifact-id is required.");
  }
  if (!args.outputPath) {
    throw new Error("--output-path is required.");
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const token = process.env[args.tokenEnvName] || process.env.GH_TOKEN;
  if (!token) {
    throw new Error(`Missing GitHub token. Set ${args.tokenEnvName} or GH_TOKEN in the process environment.`);
  }
  const url = `https://api.github.com/repos/${args.owner}/${args.repo}/actions/artifacts/${args.artifactId}/zip`;
  let response;
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    try {
      response = await fetch(url, {
        redirect: "follow",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Accept": "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "OMPCP-Codex-Artifact-Downloader",
        },
      });
      break;
    } catch (error) {
      if (attempt === 5) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 500 * attempt));
    }
  }
  if (!response) {
    throw new Error("GitHub artifact download failed before response.");
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  if (!response.ok) {
    let detail = bytes.toString("utf8");
    try {
      const parsed = JSON.parse(detail);
      detail = parsed.message || detail;
    } catch {
      // Keep raw detail.
    }
    throw new Error(`GitHub artifact download failed: ${response.status} ${detail}`);
  }
  const outputPath = path.resolve(args.outputPath);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, bytes);
  console.log(`artifact_downloaded=${outputPath}`);
  console.log(`artifact_size_bytes=${bytes.length}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
