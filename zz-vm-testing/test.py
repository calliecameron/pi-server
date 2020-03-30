from conftest import Net, Vagrant

class TestReachability:
    def test_base(self, net: Net) -> None:
        # Base reachability when all VMs are up
        net.assert_reachability({
            'internet': ['external', 'internet'],
            'router1': ['external', 'internet', 'router1_lan', 'router1_wan', 'pi1'],
            'router2': ['external', 'internet', 'router2_lan', 'router2_wan', 'pi2'],
            'pi1': ['external', 'internet', 'router1_lan', 'router1_wan', 'pi1'],
            'pi2': ['external', 'internet', 'router2_lan', 'router2_wan', 'pi2']})

    def test_no_internet(self, net: Net, vagrant: Vagrant) -> None:
        # If internet is down, nothing can reach the outside world
        vagrant.down('internet')
        net.assert_reachability({
            'router1': ['router1_lan', 'router1_wan', 'pi1'],
            'router2': ['router2_lan', 'router2_wan', 'pi2'],
            'pi1': ['router1_lan', 'router1_wan', 'pi1'],
            'pi2': ['router2_lan', 'router2_wan', 'pi2']})

    def test_no_router(self, net: Net, vagrant: Vagrant) -> None:
        # If a router is down, that LAN can't access any other network
        vagrant.down('router1')
        net.assert_reachability({
            'internet': ['external', 'internet'],
            'router2': ['external', 'internet', 'router2_lan', 'router2_wan', 'pi2'],
            'pi1': ['pi1'],
            'pi2': ['external', 'internet', 'router2_lan', 'router2_wan', 'pi2']})
