Make sure the external storage is attached and correctly formatted: should have two ext4 partitions, one for primary data storage, and one for backups. (Additional partitions for other things are OK.) The /dev nodes for these partitions should have been set already in ./01-vars.

When formatting the drives, you may want to use 'mkfs.ext4 -E lazy_itable_init=0,lazy_journal_init=0' to save the Pi from having to initialise everything.
