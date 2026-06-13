#!/usr/bin/env node

import { existsSync, cpSync, mkdirSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const importProfile = process.argv[2] === "--import-profile";

if (process.argv[2] && process.argv[2] !== "--import-profile") {
	console.log("Usage: browser-start.js [--import-profile]");
	console.log("\nOptions:");
	console.log("  --import-profile  Replace the browser-tools profile with your default Chrome profile");
	process.exit(1);
}

const HOME_DIR = os.homedir();
const SCRAPING_DIR = path.join(HOME_DIR, ".cache", "browser-tools");
const LOCK_FILES = ["SingletonLock", "SingletonSocket", "SingletonCookie"];
const SESSION_FILES = ["Current Session", "Current Tabs", "Last Session", "Last Tabs"];

function getChromeUserDataDir() {
	if (process.platform === "darwin") {
		return path.join(HOME_DIR, "Library", "Application Support", "Google", "Chrome");
	}

	if (process.platform === "win32") {
		if (!process.env.LOCALAPPDATA) {
			throw new Error("LOCALAPPDATA is not set");
		}

		return path.join(process.env.LOCALAPPDATA, "Google", "Chrome", "User Data");
	}

	return path.join(HOME_DIR, ".config", "google-chrome");
}

function findOnPath(command) {
	const lookupCommand = process.platform === "win32" ? "where" : "which";
	const result = spawnSync(lookupCommand, [command], {
		stdio: "pipe",
		encoding: "utf8",
	});

	if (result.status !== 0) {
		return null;
	}

	return result.stdout
		.split(/\r?\n/)
		.map((line) => line.trim())
		.find(Boolean) || null;
}

function findChromeExecutable() {
	let candidates;

	if (process.platform === "darwin") {
		candidates = [
			"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
			"/Applications/Chromium.app/Contents/MacOS/Chromium",
		];
	} else if (process.platform === "win32") {
		candidates = [
			path.join(process.env.PROGRAMFILES || "", "Google", "Chrome", "Application", "chrome.exe"),
			path.join(process.env["PROGRAMFILES(X86)"] || "", "Google", "Chrome", "Application", "chrome.exe"),
			path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe"),
		];
	} else {
		candidates = ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"];
	}

	for (const candidate of candidates) {
		if (!candidate) {
			continue;
		}

		if (path.isAbsolute(candidate) && existsSync(candidate)) {
			return candidate;
		}

		if (!path.isAbsolute(candidate)) {
			const resolved = findOnPath(candidate);
			if (resolved) {
				return resolved;
			}
		}
	}

	throw new Error(`Could not find a Chrome or Chromium executable for platform: ${process.platform}`);
}

function copyProfile(sourceDir, destinationDir) {
	cpSync(sourceDir, destinationDir, {
		recursive: true,
		filter: (source) => {
			const relativePath = path.relative(sourceDir, source);

			if (!relativePath) {
				return true;
			}

			const basename = path.basename(source);
			if (LOCK_FILES.includes(basename) || SESSION_FILES.includes(basename)) {
				return false;
			}

			return !relativePath.split(path.sep).includes("Sessions");
		},
	});
}

async function waitForChrome() {
	for (let i = 0; i < 30; i++) {
		try {
			const browser = await puppeteer.connect({
				browserURL: "http://localhost:9222",
				defaultViewport: null,
			});
			await browser.disconnect();
			return true;
		} catch {
			await new Promise((resolve) => setTimeout(resolve, 500));
		}
	}

	return false;
}

try {
	const browser = await puppeteer.connect({
		browserURL: "http://localhost:9222",
		defaultViewport: null,
	});
	await browser.disconnect();
	console.log("Chrome already running on :9222");
	process.exit(0);
} catch {}

if (importProfile) {
	const profileDir = getChromeUserDataDir();

	if (!existsSync(profileDir)) {
		console.error(`Chrome profile directory not found: ${profileDir}`);
		process.exit(1);
	}

	console.log("Importing Chrome profile...");

	try {
		rmSync(SCRAPING_DIR, { recursive: true, force: true });
		copyProfile(profileDir, SCRAPING_DIR);
	} catch (error) {
		console.error("Failed to import Chrome profile :(");
		if (error?.code === "EBUSY" || error?.code === "EPIPE") {
			console.error("  Close Chrome completely, including any background processes, then rerun:");
			console.error("  browser-start.js --import-profile");
			process.exit(1);
		}
		if (error?.message) {
			console.error(`  Details: ${error.message}`);
		}
		process.exit(1);
	}
} else {
	mkdirSync(SCRAPING_DIR, { recursive: true });
	for (const file of LOCK_FILES) {
		rmSync(path.join(SCRAPING_DIR, file), { force: true });
	}
}

const chromeExecutable = findChromeExecutable();
spawn(
	chromeExecutable,
	[
		"--remote-debugging-port=9222",
		`--user-data-dir=${SCRAPING_DIR}`,
		"--no-first-run",
		"--no-default-browser-check",
	],
	{ detached: true, stdio: "ignore" },
).unref();

if (!(await waitForChrome())) {
	console.error("Failed to connect to Chrome :(");
	process.exit(1);
}

console.log(`Chrome started on :9222${importProfile ? " using imported profile" : ""}`);
