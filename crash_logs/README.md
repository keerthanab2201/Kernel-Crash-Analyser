# Crash log data

The `.log` files in this directory are small synthetic parser fixtures, not a real
evaluation dataset. They must not be counted as collected crashes or reported as
model results.

For an actual study, record provenance for every public log in `labels.csv`, retain
the syzbot report URL, and review the source's current terms before redistribution.
Syzbot reports link to raw console output, symbolized reports, kernel configuration,
and (when available) reproducers. The syzkaller repository itself is Apache-2.0;
that does not automatically establish the licensing status of every linked mailing
list message or kernel log. Prefer storing source URLs plus a documented acquisition
script over redistributing a copied corpus until the data-use basis is reviewed.

QEMU-generated logs should record kernel commit, config, architecture, module source,
trigger command, and whether the observed trace exactly matches the injected cause.

