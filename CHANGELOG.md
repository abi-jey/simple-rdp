# Changelog

## 0.8.10

- Preserve case and keyboard-layout independence in `send_text()`; encode
  supplementary Unicode characters as UTF-16 surrogate pairs. Fixes #4.
- Read complete X.224 and CredSSP frames across fragmented TCP reads and reject
  truncated negotiation responses. Fixes #5.
- Preserve delayed packets and disconnect cleanly on server EOF. Fixes #6.
- Clean up failed or cancelled connection setup and stop capture before shutting
  down the encoder. Fixes #7.
- Correct RLE foreground/background decoding across the first scanline in both
  Rust implementations. Fixes #8.
- Reject invalid RLE dimensions, unsupported bit depths and decoded allocations
  exceeding 64 MiB with `ValueError`. Fixes #9.
- Drain encoder output before closing recordings, deliver small video chunks
  promptly, clean up encoder startup failures and preserve the source recording
  if transcoding fails. Fixes #10.
- Report the installed distribution version and refresh Python lockfiles during
  automated version bumps. Fixes #11.
- Update Python dependencies and tooling, PyO3 to 0.30.1, and both Python
  lockfiles. Langfuse stays on the compatible 4.15.x series because Google ADK
  2.13 requires OpenTelemetry <=1.44. Install the LiteLLM integration directly
  instead of ADK's broad `extensions` extra, whose CrewAI dependency conflicts
  on Python 3.11.
- Add regression coverage and run recording tests with ffmpeg on Linux CI.
- Bound CI utility waits and avoid reinstalling ffmpeg on runners that already
  provide it; a stalled coverage service does not block package builds.

Known follow-ups: configurable TLS certificate validation (#12) and correcting
the separate dev-release artifact publishing path (#13).
