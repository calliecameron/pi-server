# NOTE: this file isn't executable because it's so dangerous!

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" &&
source "${DIR}/common.bash" &&


echo 'This will completely purge an owncloud installation, including any user data! Use with caution!' &&
enter-to-continue &&

read -s -p 'Enter the database root password (created when installing mysql): ' DATABASE_ROOT_PW && echo &&

sudo service nginx stop &&
sudo service php5-fpm stop &&

sudo apt-get --auto-remove --purge owncloud &&
sudo rm -rf /var/www/owncloud &&
sudo rm -rf "${PI_SERVER_OWNCLOUD_DATA_PATH}" &&

mysql --user=root "--password=${DATABASE_ROOT_PW}" <<EOF &&
DROP DATABASE ${PI_SERVER_OWNCLOUD_DB};
EOF

sudo rm -f '/etc/nginx/sites-enabled/owncloud' &&


sudo service mysql restart &&
sudo service php5-fpm restart &&
sudo service nginx restart
