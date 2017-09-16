# Setup an encrypted file for CA storage

```
sudo swapoff -a
tomb dig -s <size_MB> <file>
tomb forge <keyfile>
tomb lock -k <keyfile> <file>
sudo swapon -a
```

# Mount the file

```
tomb open -k <keyfile> <file>
```

# Unmount the file

```
tomb close <name>
```
