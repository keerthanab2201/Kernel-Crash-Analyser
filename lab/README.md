# Disposable Linux fault lab

The host runner boots a diskless QEMU x86_64 guest with TCG and no network. It
creates a deterministic initramfs, triggers one failure, captures serial output,
and records input/log hashes. It never loads a module into the host kernel.

Prerequisites: Linux build environment, QEMU, a chosen Linux source revision, and
a statically linked x86_64 BusyBox with sh/mount/grep/insmod/poweroff applets. No
kernel images or verified logs are bundled. These instructions and archive tests
do not constitute a successful VM execution.

In the Linux source tree, record `git rev-parse HEAD`, create a defconfig, merge
`lab/kernel.config.fragment` using `scripts/kconfig/merge_config.sh`, run
`make olddefconfig`, and build `bzImage` and modules. Inspect the final `.config`:
dependency resolution can drop requested options. Build the example module with
`make -C /path/to/project/lab KDIR=/path/to/linux` against that same tree.

From the project root, on the machine containing QEMU:

```
python -m src.cli lab-capture --kernel /path/to/linux/arch/x86/boot/bzImage --config /path/to/linux/.config --busybox /path/to/static/busybox --kernel-revision YOUR_COMMIT --action panic --output lab-runs/panic-001
```

Other LKDTM actions: `null`, `overflow`, `uaf`. Check the guest's available DIRECT
actions; absent actions or failed boots are failed experiments, never valid labels.
For the C example, add `--module /path/to/lab/kca_demo.ko` and use `module-uaf` or
`module-fixed`. The latter reads before freeing; expect value=42 and no KASAN
finding. The buggy path ends ownership before its last consumer and should produce
a KASAN report on the instrumented guest. An emitted trigger is not evidence that
the intended failure occurred. Review the serial output before labeling.

All captures start as `pending_review`. Verify the observed stack, allocation/free
evidence and action; then add a reviewed incident to the benchmark manifest. Keep
the raw trace. LKDTM trigger strings and descriptive function names can leak labels:
evaluate full and masked views, document the masking, and keep both in one bug
family/split. Repeated boots are not independent root causes.

Reference: https://docs.kernel.org/fault-injection/provoke-crashes.html
