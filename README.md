These are the scripts I use to setup and manage my Raspberry Pi home server. Nothing fancy, just a basic Raspbian setup with:

- SSH
- OpenVPN
- SyncThing
- a media server

plus some stuff for generating and managing keys. Intended usage is for the VPN to be accessible through the home router's firewall, with everything else accessible only to machines on the LAN or through the VPN.

It's also set up so that a second Pi on another LAN somewhere else can connect to the first, and they will maintain a site-to-site VPN with each other, so that clients on either LAN have full access to both networks. The intended usage for this is so that the two side's syncthing instances can talk without having to be exposed to the internet.


To do:

- finish the syncthing backup thing
- convert the custom shell scripts to something standard, e.g. ansible and jinja2
