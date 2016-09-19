import docker
import time

class DockerWorker(object):

  def __init__(self, module):
    self.module = module
    self.params = self.module.params
    self.changed = False
    self.dc = docker.Client()
  
  def check_container(self):
    find_name = '/{}'.format(self.params.get('name'))
    for cont in self.dc.containers(all=True):
      if find_name in cont['Names']:
        return cont

  def _graceful_stop(self, name):
    timeout = self.params.get('graceful_timeout')
    signal = self.params.get('graceful_signal')
    if not timeout:
      module.fial_json(
        msg='Flag "graceful" requires parameter: graceful_timeout',
        failed=True
      )
    elif not signal:
      module.fial_json(
        msg='Flag "graceful" requires parameter: graceful_signal',
        failed=True
      )
    else:
      self.dc.kill(name, signal)
      start_time = time.time()
      while True:
        cont = self.check_container()
        if cont['Status'].startswith('Exited '):
          break
        elif timeout > 0 and time.time() > start_time + timeout:
          self.dc.kill(name)
          break
        time.sleep(1)

  def _rename_container(self, name):
    new_name = name + "-old"
    self.dc.rename(name, new_name)

  def start_container(self):
    name = self.params.get('name')
    image = self.params.get('image')
    graceful = self.params.get('graceful')
    
    if graceful:
      self._rename_container(name)
    
    self.dc.create_container(
      name=name,
      image=image
    )
    self.dc.start(name)

  def stop_container(self):
    name = self.params.get('name')
    container = self.check_container()
    
    if not container:
      self.module.fail_json(
        msg="No such container: {} to stop".format(name))
    elif not container['Status'].startswith('Exited '):
      self.changed = True
      graceful = self.params.get('graceful')
      if graceful:
        self._graceful_stop(name)
      else:
        self.dc.stop(name)
    
  def remove_container(self):
    name = self.params.get('name')
    cont = self.check_container()

    if not cont['Status'].startswith('Exited '):
      graceful = self.params.get('graceful')
      if graceful:
        self._graceful_stop(name)
      else:
        self.dc.stop(name)
        self.dc.wait(name)
      
    self.dc.remove_container(name)
    
    
def main():
  args = dict(
    action=dict(required=True, type='str'),
    name=dict(required=True, type='str'),
    image=dict(required=False, type='str'),
    graceful=dict(required=False, type='bool', default=False),
    graceful_timeout=dict(required=False, type='int'),
    graceful_signal=dict(required=False, type='str')
  )
  module = AnsibleModule(argument_spec=args)

  try:
    dw = DockerWorker(module)
    result = bool(getattr(dw, module.params.get('action'))())
    module.exit_json(changed=dw.changed, result=result)
  except Exception:
    module.exit_json(failed=True, changed=True, msg="error")

  module.exit_json()


from ansible.module_utils.basic import *
if __name__ == '__main__':
  main()
