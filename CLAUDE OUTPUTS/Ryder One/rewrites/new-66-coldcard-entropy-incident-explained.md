# The Coldcard Entropy Incident, Explained: What It Means for Your Bitcoin

On July 30, 2026, Coinkite [disclosed](https://blog.coinkite.com/coldcard-mk3-seed-generation-warning/) that some Coldcard firmware versions had been generating wallet seeds with far less randomness than designed. Attackers found the weakness before most owners did. Within days, roughly 1,816 BTC, worth close to 116 million USD, had been [drained from more than 5,200 addresses](https://www.trmlabs.com/resources/blog/the-largest-hardware-wallet-exploit-of-2026-inside-the-usd-116-million-coldcard-hack), making this the largest [hardware wallet](https://ryder.id/blogs/glossary/what-is-a-hardware-wallet-simple-definition-how-it-works) exploit of 2026. If you own a Coldcard, this article explains what went wrong, whether your coins are exposed, and what to do today. If you don't, the lesson still matters, because the failure pattern behind it can reach any wallet that puts everything behind one device and one backup.

One thing before we start. We make a competing wallet, so this piece could easily read as a victory lap, and it shouldn't. Coinkite disclosed fast, shipped fixes for every affected model within days, and published the full technical detail for anyone to check. Our goal here is to explain the mechanics, because they show how "keys generated offline on dedicated hardware" can still fail, and what structural protection against that kind of failure looks like.

## What happened to Coldcard

The root cause was a build configuration error, and Coinkite's own [technical backgrounder](https://blog.coinkite.com/entropy-technical-backgrounder/) lays it out with unusual candor. A check in the firmware build tested whether a configuration setting existed rather than whether it was switched on. Because of that one-line mistake, the build completed cleanly while seed generation quietly fell back on Yasmarang, a software pseudorandom number generator bundled with MicroPython, instead of the STM32 chip's hardware randomness source. The flaw entered Coldcard firmware with version 4.0.1 in March 2021 and sat there for five years.

Then someone found it. According to [TRM Labs](https://www.trmlabs.com/resources/blog/the-largest-hardware-wallet-exploit-of-2026-inside-the-usd-116-million-coldcard-hack), the first theft wave moved roughly 594 BTC, around 38 million USD, out of about 500 wallets in 25 minutes. Three more waves followed over the next days, and by early August the running tally compiled by Galaxy Research stood near 1,816 BTC. The attackers never needed to touch a single device; a weak seed can be recomputed and swept from anywhere on earth.

## What entropy means for your private key

Entropy is unpredictability, measured in bits. A [private key](https://ryder.id/blogs/glossary/what-is-a-private-key) is a very large random number, and a [seed phrase](https://ryder.id/blogs/glossary/what-is-a-seed-phrase) is a human-readable encoding of one. When a wallet promises 128 bits of entropy, it means an attacker would have to search 2^128 possibilities to find your key, a number so large that every computer on earth working together couldn't cover a fraction of it in your lifetime.

A weak generator collapses that search space. Coinkite's analysis puts affected Mk2 and Mk3 seeds at [roughly 40 bits of effective entropy, with Mk4, Mk5 and Q seeds at roughly 72 bits](https://blog.coinkite.com/entropy-technical-backgrounder/). Forty bits is about one trillion possibilities. That sounds like plenty until you remember that rented computing power can walk through a trillion candidate seeds in hours, checking each one against addresses that hold a balance. The chip was never broken and the hardware did its job; the firmware just never asked it for the numbers.

## Who is affected, and what to do now

Per [Coinkite's advisory](https://blog.coinkite.com/coldcard-mk3-seed-generation-warning/), the affected range covers Mk2 and Mk3 devices on firmware 4.0.1 through 4.1.9, Mk4 and Mk5 devices before version 5.6.0, and Q devices before 1.5.0Q. Fixed firmware now exists for every affected model. Coinkite names two exceptions where a seed is considered safe: seeds built with at least 50 fair, private dice rolls, and wallets protected by a strong, unique BIP-39 passphrase. TAPSIGNER, OPENDIME and SATSCARD are unaffected.

If you generated a seed on an affected Coldcard, treat that seed as compromised even if your firmware is current today, because an update can't repair a seed that already exists. Here is the migration path:

1. Update to the fixed firmware for your model.
2. Generate a brand-new seed on the updated device.
3. Send a small test transaction to the new wallet and confirm it arrives.
4. Move the rest of your balance, then retire the old seed for good.

Move calmly but don't wait for a quiet weekend. The theft waves show that attackers are working through the list of exposed addresses faster than holders are migrating off them.

## The deeper lesson: one device, one point of failure

The uncomfortable part of this story is that Coldcard owners followed the standard [self-custody](https://ryder.id/blogs/glossary/what-is-self-custody) playbook to the letter. They bought dedicated hardware, they kept their keys offline, and many stamped their seed phrases into metal plates built to survive fires and floods. None of it helped, because the seed itself was born guessable. A metal backup is a sensible upgrade from paper, yet it can only preserve the seed it's given; when that seed was predictable from day one, the steel preserved a weakness.

When key generation, storage and backup all trace back to a single device and a single object, one silent flaw anywhere in that chain exposes everything at once. Security engineers call this a single point of failure, and the Coldcard entropy incident is the clearest demonstration of the concept in years. The fix isn't to abandon hardware wallets, which remain far safer than exchanges or hot wallets; the fix is to stop accepting designs where one mistake is unrecoverable.

## How Ryder One handles key generation and recovery

We built [Ryder One](https://ryder.id/products/ryder-one) on the assumption that any single component can fail, including ours. Private keys are generated inside an EAL6+ certified Infineon SLC38 secure element and never leave it. The firmware was independently audited by Halborn, and the [full report is public](https://www.halborn.com/audits/ryder/secure-element-783ea4): zero critical findings, zero high findings, and every issue resolved. No wallet company should ask you to take its randomness on faith, which is why outside review before launch mattered to us.

No audit makes a software mistake impossible, and we won't pretend ours does; what changes the outcome is whether one mistake can cost you everything. That's what [TapSafe Recovery](https://ryder.id/blogs/post/tapsafe-recovery-explained-the-seed-phrase-alternative-built-into-ryder-one) is for. TapSafe splits wallet recovery across a Recovery Tag holding 50%, an encrypted phone backup holding the other 50% in your iCloud or Google Drive, and optional Recovery Contacts holding 25% each. No single piece grants access on its own, so losing one object, or discovering a flaw in one layer, doesn't hand your Bitcoin to a stranger. The seed phrase stays accessible on-device as a last resort and follows the BIP-39 standard, so you're never locked to our hardware either.

## Where to go from here

If you hold coins on an affected Coldcard, migrate now using the steps above; that's the urgent part, and it doesn't require buying anything from us. If this incident has you rethinking how your Bitcoin setup handles failure, look at where your own single points of failure sit. The [Ryder One](https://ryder.id/products/ryder-one) Starter Combo is 149 USD, ships free worldwide with a Recovery Tag, wireless charger and pouch in the box, and sets up in about 60 seconds. Your keys should survive a bad day, whether that day involves a lost device, a forgotten PIN, or a bug nobody caught for five years.
