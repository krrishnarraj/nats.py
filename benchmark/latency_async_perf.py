import argparse, sys
import asyncio
import time
from random import randint
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrTimeout

DEFAULT_ITERATIONS = 10000
HASH_MODULO = 250

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

def show_usage():
  message = """
Usage: latency_perf [options]

options:
  -n ITERATIONS                    Iterations to spec (default: 1000)
  -S SUBJECT                       Send subject (default: (test)
  """
  print(message)

def show_usage_and_die():
  show_usage()
  sys.exit(1)

global received
received = 0

async def main(loop):
  parser = argparse.ArgumentParser()
  parser.add_argument('-n', '--iterations', default=DEFAULT_ITERATIONS, type=int)
  parser.add_argument('-S', '--subject', default='test')
  parser.add_argument('--servers', default=[], action='append')
  args = parser.parse_args()

  servers = args.servers
  if len(args.servers) < 1:
    servers = ["nats://127.0.0.1:4222"]
  opts = { "servers": servers }

  # Make sure we're connected to a server first...
  nc = NATS()
  try:
    await nc.connect(**opts)
  except Exception as e:
    sys.stderr.write(f"ERROR: {e}")
    show_usage_and_die()

  async def handler(msg):
    await nc.publish(msg.reply, b'')
  await nc.subscribe(args.subject, cb=handler)
  await nc.flush()

  # Start the benchmark
  start = time.monotonic()
  to_send = args.iterations
  failures = 0

  print("Sending {} request/responses on [{}]".format(
      args.iterations, args.subject))
  while to_send > 0:
    to_send -= 1
    if to_send == 0:
      break

    try:
      response = await nc.request(args.subject, b'', timeout=0.5)
    except ErrTimeout:
      failures += 1
    
    if (to_send % HASH_MODULO) == 0:
      sys.stdout.write("#")
      sys.stdout.flush()

  duration = time.monotonic() - start
  ms = "%.2f" % ((duration/args.iterations) * 1000)
  print(f"\nTest completed : {ms} ms avg request/response latency (failures={failures})")
  await nc.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
    loop.close()
