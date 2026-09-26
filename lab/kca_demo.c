// SPDX-License-Identifier: GPL-2.0
// Educational lifetime example. Load only in the disposable KCA QEMU guest.
#include <linux/init.h>
#include <linux/module.h>
#include <linux/slab.h>

static bool inject_uaf;
module_param(inject_uaf, bool, 0400);
MODULE_PARM_DESC(inject_uaf, "Deliberately read freed memory (QEMU guest only)");

static noinline int read_value(const int *value)
{
	return READ_ONCE(*value);
}

static int __init kca_demo_init(void)
{
	int result;
	int *value = kmalloc(sizeof(*value), GFP_KERNEL);
	if (!value)
		return -ENOMEM;
	*value = 42;
	if (inject_uaf) {
		/* Bug: ownership ends at kfree, before the last consumer executes. */
		kfree(value);
		result = read_value(value);
	} else {
		/* Fix: keep ownership until the synchronous consumer has finished. */
		result = read_value(value);
		kfree(value);
	}
	pr_info("kca_demo: read completed value=%d\n", result);
	return 0;
}

static void __exit kca_demo_exit(void) {}
module_init(kca_demo_init);
module_exit(kca_demo_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Controlled lifetime fault and fixed path for KCA evaluation");
