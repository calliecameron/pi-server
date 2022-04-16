# Encryption

The CA should be in an encrypted directory, e.g. using `tomb`.

## Setup an encrypted file for CA storage

```shell
sudo swapoff -a
tomb dig -s <size_MB> <file>
tomb forge <keyfile>
tomb lock -k <keyfile> <file>
sudo swapon -a
```

## Mount the file

```shell
tomb open -k <keyfile> <file>
```

## Unmount the file

```shell
tomb close <name>
```
