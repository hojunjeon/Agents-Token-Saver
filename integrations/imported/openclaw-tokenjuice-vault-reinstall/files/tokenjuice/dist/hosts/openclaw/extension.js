import { compactBashResult, getOutputAwareInspectionSkipReason } from "../../core/integrations/compact-bash-result.js";
import { buildCompactionNotice, buildTokenjuiceDetails, extractTextContent, mergeDetails, } from "../shared/tool-result.js";
import { formatErrorMessage } from "../pi/extension/utils.js";
const DEFAULT_MAX_INLINE_CHARS = 1200;
const GENERIC_FALLBACK_MIN_SAVED_CHARS = 120;
const GENERIC_FALLBACK_MAX_RATIO = 0.75;
const OPENCLAW_TOKENJUICE_ARTIFACT_DIR = "/home/ubuntu/.openclaw/token-vault/artifacts";
const SIGNAL_LINE_PATTERN = /\b(error|exception|traceback|failed|failure|warning|warn|critical|fatal|denied|timeout|not found|no such file|assert)\b/i;
const MAX_SIGNAL_LINES = 24;
function isRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
function isExecLikeToolName(toolName) {
    return toolName === "exec" || toolName === "bash";
}
function readCommand(input) {
    return isRecord(input) && typeof input.command === "string" ? input.command : "";
}
function readCwd(input, details, fallback) {
    if (isRecord(input) && typeof input.workdir === "string" && input.workdir.trim()) {
        return input.workdir;
    }
    if (isRecord(details) && typeof details.cwd === "string" && details.cwd.trim()) {
        return details.cwd;
    }
    return fallback;
}
function readsOpenClawTokenVaultArtifact(command) {
    return command.includes("/.openclaw/token-vault/artifacts/");
}
function readAggregatedText(details, content) {
    if (isRecord(details) && typeof details.aggregated === "string") {
        return details.aggregated;
    }
    return extractTextContent(content);
}
function readExitCode(details, isError) {
    if (isRecord(details) && typeof details.exitCode === "number") {
        return details.exitCode;
    }
    return isError ? 1 : 0;
}
function isCompletedExecDetails(details) {
    if (!isRecord(details)) {
        return false;
    }
    return details.status === "completed" || details.status === "failed";
}
function extractSignalLines(text, inlineText) {
    const signals = [];
    const alreadyIncluded = new Set(inlineText.split(/\r?\n/u).map((line) => line.trim()));
    const lines = text.split(/\r?\n/u);
    for (let index = 0; index < lines.length; index += 1) {
        const line = lines[index].trim();
        if (!line || !SIGNAL_LINE_PATTERN.test(line) || alreadyIncluded.has(line)) {
            continue;
        }
        signals.push(`${index + 1}: ${line.slice(0, 240)}`);
        if (signals.length >= MAX_SIGNAL_LINES) {
            break;
        }
    }
    return signals;
}
function appendSignalLines(inlineText, rawText) {
    const signalLines = extractSignalLines(rawText, inlineText);
    if (signalLines.length === 0) {
        return inlineText;
    }
    return `${inlineText}\n\nHigh-signal lines:\n${signalLines.join("\n")}`;
}
export function createTokenjuiceOpenClawEmbeddedExtension() {
    return function tokenjuiceOpenClawExtension(pi) {
        pi.on("tool_result", async (rawEvent, ctx) => {
            const event = rawEvent;
            if (!isExecLikeToolName(event.toolName)) {
                return undefined;
            }
            if (!isCompletedExecDetails(event.details)) {
                return undefined;
            }
            const command = readCommand(event.input);
            if (!command) {
                return undefined;
            }
            if (readsOpenClawTokenVaultArtifact(command)) {
                return undefined;
            }
            const outputText = readAggregatedText(event.details, event.content);
            if (!outputText.trim()) {
                return undefined;
            }
            const executionInput = {
                toolName: "exec",
                command,
                combinedText: outputText,
            };
            if (getOutputAwareInspectionSkipReason("allow-safe-inventory", executionInput)) {
                return undefined;
            }
            try {
                const outcome = await compactBashResult({
                    source: "openclaw",
                    command,
                    cwd: readCwd(event.input, event.details, ctx.cwd),
                    visibleText: outputText,
                    exitCode: readExitCode(event.details, Boolean(event.isError)),
                    maxInlineChars: DEFAULT_MAX_INLINE_CHARS,
                    inspectionPolicy: "allow-safe-inventory",
                    minSavedCharsAny: 8,
                    genericFallbackMinSavedChars: GENERIC_FALLBACK_MIN_SAVED_CHARS,
                    genericFallbackMaxRatio: GENERIC_FALLBACK_MAX_RATIO,
                    skipGenericFallbackForCompoundCommands: true,
                    storeRaw: true,
                    storeDir: OPENCLAW_TOKENJUICE_ARTIFACT_DIR,
                    metadata: {
                        source: "openclaw-tool-result",
                    },
                });
                if (outcome.action === "keep") {
                    return undefined;
                }
                return {
                    content: [
                        {
                            type: "text",
                            text: `${appendSignalLines(outcome.result.inlineText, outputText)}\n\n[${buildCompactionNotice(outcome.result)}]`,
                        },
                    ],
                    details: mergeDetails(event.details, buildTokenjuiceDetails(outcome.result)),
                };
            }
            catch (error) {
                throw new Error(`tokenjuice failed to compact OpenClaw exec output: ${formatErrorMessage(error)}`);
            }
        });
    };
}
