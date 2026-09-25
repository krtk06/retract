import { defineSandbox } from "eve/sandbox";

import { environment } from "../../lib/sandbox";

export { environment };
export default defineSandbox(() => environment.open());
