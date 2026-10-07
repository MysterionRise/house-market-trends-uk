import next from "eslint-config-next";

const config = [...next, { ignores: ["lib/contracts.gen.ts", ".next/**", "public/**"] }];

export default config;
