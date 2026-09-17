# Freqtrade Dry-run

This adapter runs only from an approved `candidate-v*` release. It does not mount exchange credentials and cannot be used when Freqtrade reports live mode.

## Frozen release contents

The external release directory must contain:

- `GovernedDryRunStrategy.py`
- `config.dry-run.json`
- `evidence.json`
- `release-manifest.toml`

The directory is mounted read-only. The strategy performs a full GitHub-backed release check at startup and refreshes it once per minute. Immediately before every entry, it rechecks the local commit, annotated tag, manifest and artifact hashes without making a network request. A full approval older than five minutes blocks entry.

## Local runtime

Copy `deploy/freqtrade-dry-run/.env.example` to `.env`, set the absolute candidate release directory, and replace every authentication placeholder with a random local value. Do not add Binance keys.

The dedicated Compose service uses:

- container `freqtrade-dry-run`;
- host URL `http://127.0.0.1:8081`;
- a named Dry-run volume and `tradesv3.dry-run.sqlite`;
- one BTC futures pair, isolated margin, one open position, 1x leverage and at most 10 simulated USDT per entry.

The strategy emits no automatic entries. A standard test episode may use FreqUI force-entry and force-exit only after the candidate release is approved and the Web UI shows Dry-run mode.
