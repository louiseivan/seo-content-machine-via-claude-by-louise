# Trezor Safe 7: What's New, and How It Compares to Ryder One

Trezor introduced the Trezor Safe 7 on [October 21, 2025](https://trezor.io/blog/news/meet-trezor-safe-7-the-first-quantum-ready-hardware-wallet-with-a-next-gen-secure-element-chip) as its first wireless device: Bluetooth, wireless charging, a 2.5-inch color touchscreen, and a new secure element from its sister company Tropic Square, priced at [249 USD](https://trezor.io/trezor-safe-7). It's the most ambitious [hardware wallet](https://ryder.id/blogs/glossary/what-is-a-hardware-wallet-simple-definition-how-it-works) Trezor has built. The hardware is new from the ground up, though the custody model underneath is the one Trezor has used since 2014: your wallet is backed up by words you write down, and your recovery depends on those words surviving. We make the [Ryder One](https://ryder.id/products/ryder-one), which takes a different path, so you know where we stand. What follows is a fair look at both devices, with every Safe 7 spec sourced from Trezor's own pages, so you can decide which model fits how you want to hold your crypto.

## What's new in the Trezor Safe 7

The headline change is wireless. The Safe 7 pairs with your phone over [Bluetooth 5.0+ using an encrypted, open-source protocol](https://trezor.io/trezor-safe-7), keeps a USB port for wired use, and charges on Qi2-compatible pads through a 330 mAh LiFePO4 battery. In hand it's an anodized aluminum unibody measuring 75.4 x 44.5 x 8.3 mm and weighing 45 g, with a 2.5-inch, 520 x 380 pixel color touchscreen under Gorilla Glass 3 that reaches 700 nits of brightness. This is a phone-first device, built for people who manage their crypto from a couch instead of a desk.

Under the glass sit [three chips](https://trezor.io/guides/trezor-devices/trezor-safe-7/dual-secure-elements-in-trezor-safe-7). TROPIC01, designed by Tropic Square (a SatoshiLabs company), lets independent researchers review its design without signing NDAs, which is rare in an industry where secure chips normally stay closed. Alongside it runs an EAL6+ certified Optiga Trust M from Infineon, while an STM32U5 microcontroller coordinates the two without being able to override their protections. Trezor also calls the Safe 7 [quantum-ready](https://trezor.io/blog/news/meet-trezor-safe-7-the-first-quantum-ready-hardware-wallet-with-a-next-gen-secure-element-chip): according to the company, the bootloader and device authentication are hardened against future quantum attacks.

## Where Trezor's open-source heritage counts

Trezor has published its firmware as open source for [over a decade](https://trezor.io/blog/news/meet-trezor-safe-7-the-first-quantum-ready-hardware-wallet-with-a-next-gen-secure-element-chip), and anyone who wants to check how their wallet handles their keys can go read the code. TROPIC01 extends that philosophy into silicon. That transparency is a real advantage, and we respect it. The Safe 7 also supports [thousands of coins and tokens](https://trezor.io/trezor-safe-7), including Bitcoin, Ethereum, Solana, Arbitrum, and USDC, which matters if your portfolio stretches across many chains.

**Best for:** experienced holders who want open-source hardware, wide coin support, and who are comfortable managing seed words or Shamir shares themselves.

**Worth knowing:** every recovery path on the Safe 7 still ends at words on paper or metal. If those words burn, flood, fade, or fall into the wrong hands, the newest chip in the industry can't help you. At 249 USD, it's also among the priciest mainstream wallets sold today.

## Trezor Safe 7 vs Ryder One: side by side

| | Trezor Safe 7 | Ryder One |
|---|---|---|
| Price | 249 USD | 149 USD (Starter Combo), 179 USD (Super Safe Combo) |
| Size and weight | 75.4 x 44.5 x 8.3 mm, 45 g | 41 x 55 x 14.5 mm, 38 g |
| Screen | 2.5-inch color touchscreen, 520 x 380 | 1.6-inch AMOLED touchscreen, 320 x 360 |
| Connectivity | Bluetooth 5.0+, wired USB | NFC only (no Bluetooth, no USB, no Wi-Fi) |
| Battery | 330 mAh LiFePO4, Qi2 wireless charging | 200 mAh lithium-ion, Qi wireless charging (charger included) |
| Secure elements | TROPIC01 + EAL6+ Optiga Trust M | EAL6+ Infineon SLC38 |
| Backup model | 12, 20, or 24-word backup; SLIP-39 Multi-share | TapSafe Recovery (Recovery Tag + phone, optional Recovery Contacts); BIP-39 seed on-device |
| After device loss | Restore from written words or collected shares | Recover with Recovery Tag + phone, no words to transcribe |
| Coin support | Thousands of coins and tokens | Bitcoin, Ethereum, Solana, top ERC-20 and SPL tokens |
| Audit and durability | Open-source firmware, community-reviewed | Halborn audit (0 critical, 0 high), IP67, Red Dot 2026 |

Both prices were checked on each maker's store at the time of writing.

## Backup and recovery: SLIP-39 shares vs TapSafe

Trezor's answer to the fragile single backup is [Multi-share Backup](https://trezor.io/guides/backups-recovery/advanced-wallets/multi-share-backup-on-trezor), built on the SLIP-39 standard: your wallet secret splits into multiple 20-word shares, and you choose how many are needed to recover, say 3 of 5. Spread across locations, no single fire or theft can sink you, and that's a meaningful step past the classic [seed phrase](https://ryder.id/blogs/glossary/what-is-a-seed-phrase) under the mattress. The honest catch is the homework. Each share is still a list of words a person must write correctly, store somewhere safe, remember the location of for years, and eventually type back into a device under stress.

We built [TapSafe Recovery](https://ryder.id/pages/tapsafe) to remove that homework while keeping the same cryptographic idea, since our system runs on a custom implementation of Shamir's Secret Sharing too. Your Recovery Tag, a rugged NFC tag rated IP69K, holds 50% of wallet recovery. Your paired phone holds the other 50%, stored encrypted in your iCloud or Google Drive rather than on the phone itself, so a lost phone doesn't mean a lost backup. Together they restore everything. If you want more redundancy, optional Recovery Contacts each hold 25%, and they can see nothing about your wallet or its balance. Setup happens on the device in under 60 seconds: pair your phone, tap the Tag, confirm.

TapSafe doesn't trap you in our ecosystem either. The seed phrase stays accessible on-device as a last resort, in standard BIP-39 format, so you can move to other hardware whenever you choose. The reverse works as well: if you run a Trezor today, you can import your existing 12 or 24-word phrase into Ryder One and layer TapSafe on top of it. We wrote a [full TapSafe explainer](https://ryder.id/blogs/post/tapsafe-recovery-explained-the-seed-phrase-alternative-built-into-ryder-one) if you want the details.

## Connectivity: two radios or none

Bluetooth is what makes the Safe 7 pleasant to use, and Trezor engineered it with care; the protocol is encrypted and published as open source. Every radio and port adds surface a device has to defend, though, and here the two wallets part ways. Ryder One takes the narrow route: NFC only, with no Bluetooth radio, no USB data path, and no Wi-Fi. To interact with it, you tap it against your phone from a few centimeters away, the same gesture as tap-to-pay. Before anything signs, the full transaction appears on the 1.6-inch AMOLED touchscreen for you to verify, approval requires a physical button wired directly to the EAL6+ Infineon SLC38 secure element, and the PIN keypad shuffles its layout on every unlock so nobody can learn your code by watching your fingers.

On the audit side, Trezor relies on open code and community review, which has served it well. We took the certified route and had Halborn independently audit our firmware; the [public report](https://www.halborn.com/audits/ryder/secure-element-783ea4) found 0 critical and 0 high issues. Different philosophies, both defensible, and worth weighing by which failure you consider more likely.

## Which one should you buy?

Pick the Safe 7 if you hold assets across many chains, want firmware you can read line by line, and don't mind being the custodian of your own backup words for the long haul. It's a well-built device from a company with one of the longest track records in the industry, and at 249 USD you're paying for the bigger screen, the radio, and the new chip.

Pick Ryder One if the thing you fear is loss: of the device, of the phone, of the backup, or of the discipline needed to keep word lists safe for a decade. At 149 USD for the Starter Combo (179 USD for the Super Safe Combo), it costs 100 USD less than the Safe 7, recovers with two taps instead of a transcription, and has shipped to buyers in 40+ countries with zero hacks. For most people, the wallet that survives their own mistakes beats the wallet with the longest spec sheet. If you're also weighing Ledger, we ran the [same comparison against Ledger](https://ryder.id/blogs/post/ryder-one-vs-ledger-which-hardware-wallet-is-best-for-you).

Ready to hold your crypto without betting everything on a piece of paper? [Get the Ryder One](https://ryder.id/products/ryder-one).
