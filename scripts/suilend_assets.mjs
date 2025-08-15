

import fs from 'node:fs/promises';
import { SuiClient } from '@mysten/sui/client';
import { SuilendClient, LENDING_MARKET_ID, LENDING_MARKET_TYPE } from '@suilend/sdk';

const ADDR_ENV = process.env.SUI_ADDRESSES || process.env.SUI_ADDRESS || '';
const ADDRESSES = ADDR_ENV.split(',').map((s) => s.trim()).filter(Boolean);
const RPC_URL = process.env.SUI_RPC_URL || 'https://fullnode.mainnet.sui.io:443';

function prefix(addr) { return addr.slice(0, 10); }

async function simplifyObligation(ob, reservesById) {
  // Try to project deposits/borrows with symbol/coinType/decimals/amountRaw
  const pick = (o, keys) => keys.find((k) => o && k in o);
  const arr = (o, keys) => (o && (o[keys.find((k) => Array.isArray(o[k]))] || [])) || [];

  const deposits = arr(ob, ['deposits', 'depositBalances', 'collaterals']);
  const borrows  = arr(ob, ['borrows', 'borrowBalances']);

  const mapOne = (x) => {
    // Try find reserve id
    const rid = x.reserveId || x.reserve_id || x.reserve || x.reserveID || x.reserve_id_ref || x.id || x.fields?.reserveId || x.fields?.reserve?.id;
    const res = reservesById?.get?.(rid) || reservesById?.[rid] || {};
    const symbol = x.symbol || res.symbol || res.assetSymbol || res.ticker || '';
    const coinType = x.coinType || res.coinType || res.assetType || '';
    const decimals = Number(x.decimals ?? res.decimals ?? 9);
    const amountRaw = Number(x.amount ?? x.balance ?? x.principal ?? x.deposited ?? x.depositedBalance ?? x.borrowed ?? 0);
    const amountHuman = typeof x.amountHuman === 'number' ? x.amountHuman : amountRaw / (10 ** decimals);
    return { reserveId: rid, coinType, symbol, decimals, amountRaw, amountHuman, raw: x };
  };

  return {
    deposits: deposits.map(mapOne),
    borrows: borrows.map(mapOne),
    raw: ob,
  };
}

async function main() {
  if (ADDRESSES.length === 0) {
    console.log('No addresses in SUI_ADDRESSES/SUI_ADDRESS, skipping Suilend.');
    return;
  }

  const client = new SuiClient({ url: RPC_URL });
  const suilend = await SuilendClient.initialize(LENDING_MARKET_ID, LENDING_MARKET_TYPE, client);
  // Build a reserves lookup for symbol/coinType/decimals
  const reservesArr = suilend?.reserves || suilend?.getReserves?.() || [];
  const reservesById = new Map();
  for (const r of reservesArr) {
    const id = r?.id || r?.reserveId || r?.fields?.id || r?.fields?.metadata?.id; // best effort
    if (!id) continue;
    const entry = {
      id,
      symbol: r?.symbol || r?.metadata?.symbol || r?.assetSymbol || '',
      coinType: r?.coinType || r?.metadata?.coinType || r?.assetType || '',
      decimals: Number(r?.decimals ?? r?.metadata?.decimals ?? 9),
    };
    reservesById.set(id, entry);
  }

  await fs.mkdir('data', { recursive: true });

  for (const address of ADDRESSES) {
    const caps = await SuilendClient.getObligationOwnerCaps(address, [LENDING_MARKET_TYPE], client);
    const obligations = [];
    for (const cap of caps) {
      const oid = cap?.obligationId || cap?.obligation_id || cap?.id || cap?.objectId || cap?.fields?.obligation?.id?.id;
      if (!oid) continue;
      const ob = await SuilendClient.getObligation(oid, [LENDING_MARKET_TYPE], client);
      const simp = await simplifyObligation(ob, reservesById);
      obligations.push({ obligationId: oid, ...simp });
    }

    const payload = {
      date_iso: new Date().toISOString(),
      address,
      market_id: LENDING_MARKET_ID,
      obligations,
      reserves: Array.from(reservesById.values()),
      caps,
    };

    const out = `data/suilend_${prefix(address)}.json`;
    await fs.writeFile(out, JSON.stringify(payload, null, 2));
    console.log(`wrote ${out}`);
  }
}

main().catch(async (e) => {
  console.error('Suilend fetch failed:', e?.message || e);
  try {
    await fs.mkdir('data', { recursive: true });
    await fs.writeFile('data/suilend_error.json', JSON.stringify({ error: String(e) }, null, 2));
  } catch {}
});
