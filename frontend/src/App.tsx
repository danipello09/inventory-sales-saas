import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { api, ApiError, pagePath } from "./api";
import type {
  Category,
  Movement,
  Organization,
  Page,
  Product,
  Sale,
  Stock,
  User,
} from "./api";

type View =
  | "Overview"
  | "Products"
  | "Inventory"
  | "New sale"
  | "Sales history";
const views: View[] = [
  "Overview",
  "Products",
  "Inventory",
  "New sale",
  "Sales history",
];
const icons = ["◫", "▦", "▤", "+", "↗"];
const empty = <T,>(): Page<T> => ({
  count: 0,
  next: null,
  previous: null,
  results: [],
});
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <span>◇</span>
      <p>{text}</p>
    </div>
  );
}
function Badge({ active, children }: { active: boolean; children: ReactNode }) {
  return (
    <span className={`badge ${active ? "good" : "muted"}`}>{children}</span>
  );
}
function Pager({
  page,
  onPage,
}: {
  page: Page<unknown>;
  onPage: (path: string) => void;
}) {
  return (
    <div className="pager">
      <span>{page.count} records</span>
      <div>
        <button
          className="secondary"
          disabled={!page.previous}
          onClick={() => onPage(pagePath(page.previous!))}
        >
          Previous
        </button>
        <button
          className="secondary"
          disabled={!page.next}
          onClick={() => onPage(pagePath(page.next!))}
        >
          Next
        </button>
      </div>
    </div>
  );
}

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [org, setOrg] = useState<Organization | null>(null);
  const [view, setView] = useState<View>("Overview");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [register, setRegister] = useState(false);
  const [products, setProducts] = useState(empty<Product>());
  const [categories, setCategories] = useState(empty<Category>());
  const [stock, setStock] = useState(empty<Stock>());
  const [sales, setSales] = useState(empty<Sale>());
  const [movements, setMovements] = useState(empty<Movement>());
  const [variants, setVariants] = useState([
    { sku: "", price: "", size: "", color: "" },
  ]);
  const [cart, setCart] = useState<{ variant_id: string; quantity: number }[]>(
    [],
  );
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null);
  const admin = user?.membership?.role === "ADMIN";
  function failure(cause: unknown) {
    setError(cause instanceof Error ? cause.message : "Something went wrong.");
    if (cause instanceof ApiError && cause.status === 401) {
      setUser(null);
      setOrg(null);
    }
  }
  async function load() {
    const [o, p, c, i, s, m] = await Promise.all([
      api<Organization>("organization/"),
      api<Page<Product>>("products/"),
      api<Page<Category>>("categories/?page_size=100"),
      api<Page<Stock>>("inventory/"),
      api<Page<Sale>>("sales/"),
      api<Page<Movement>>("inventory/movements/"),
    ]);
    setOrg(o);
    setProducts(p);
    setCategories(c);
    setStock(i);
    setSales(s);
    setMovements(m);
  }
  useEffect(() => {
    let active = true;
    api<User>("auth/me/")
      .then(async (u) => {
        if (active) {
          setUser(u);
          await load();
        }
      })
      .catch((cause) => {
        if (active && !(cause instanceof ApiError && cause.status === 401))
          failure(cause);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function perform(action: () => Promise<void>, message = "") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      if (message) setNotice(message);
    } catch (cause) {
      failure(cause);
    } finally {
      setBusy(false);
    }
  }
  function paginate<T>(path: string, setter: (page: Page<T>) => void) {
    void perform(async () => setter(await api<Page<T>>(path)));
  }
  function go(next: View) {
    setView(next);
    setError("");
    setNotice("");
    setSelectedSale(null);
  }
  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await perform(async () => {
      const u = await api<User>(
        register ? "auth/register/" : "auth/login/",
        "POST",
        {
          email: data.get("email"),
          password: data.get("password"),
          ...(register
            ? {
                organization_name: data.get("organization_name"),
                currency: "COP",
              }
            : {}),
        },
      );
      await load();
      setUser(u);
    });
  }
  if (loading)
    return (
      <main className="loading" role="status">
        Loading your workspace…
      </main>
    );
  if (!user)
    return (
      <main className="auth-layout">
        <section className="auth-story">
          <div className="brand">
            <span className="brand-icon">s.</span>stockroom
          </div>
          <span className="eyebrow">INVENTORY & SALES / LOCAL DEMO</span>
          <h1>
            A clear view of
            <br />
            every move.
          </h1>
          <p>
            Products, stock and sales.
            <br />
            One connected workspace for your team.
          </p>
          <div className="story-card">
            <span>↗</span>
            <h2>From shelf to sale.</h2>
            <p>
              Real transactions. Traceable movements.
              <br />
              Your organization’s data, kept separate.
            </p>
          </div>
          <small>Portfolio MVP · Not production-ready</small>
        </section>
        <section className="auth-form">
          <div className="auth-box">
            <span className="eyebrow">YOUR WORKSPACE</span>
            <h2>{register ? "Start a demo workspace" : "Welcome back"}</h2>
            <p className="subtle">
              {register
                ? "Create an organization with an ADMIN account."
                : "Sign in to keep your business moving."}
            </p>
            {error && (
              <div role="alert" className="alert">
                {error}
              </div>
            )}
            <form onSubmit={(e) => void authenticate(e)}>
              {register && (
                <Field label="Organization name">
                  <input
                    name="organization_name"
                    required
                    maxLength={160}
                    autoComplete="organization"
                  />
                </Field>
              )}
              <Field label="Email address">
                <input
                  name="email"
                  type="email"
                  required
                  autoComplete="username"
                  placeholder="you@example.com"
                />
              </Field>
              <Field label="Password">
                <input
                  name="password"
                  type="password"
                  required
                  minLength={register ? 12 : 1}
                  maxLength={128}
                  autoComplete={register ? "new-password" : "current-password"}
                />
              </Field>
              <button className="primary full" disabled={busy}>
                {busy
                  ? "Please wait…"
                  : register
                    ? "Create workspace →"
                    : "Sign in →"}
              </button>
            </form>
            <button
              className="text-button"
              disabled={busy}
              onClick={() => {
                setRegister(!register);
                setError("");
              }}
            >
              {register
                ? "Already have an account? Sign in"
                : "New here? Create a demo workspace"}
            </button>
            <p className="auth-foot">
              Session cookies + CSRF protection.
              <br />
              Credentials are never stored in browser storage.
            </p>
          </div>
        </section>
      </main>
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={() => go("Overview")}>
          <span className="brand-icon">s.</span>stockroom
        </a>
        <div className="workspace">
          <span className="avatar">{org?.name.charAt(0) ?? "W"}</span>
          <div>
            <strong>{org?.name ?? "Workspace"}</strong>
            <small>{user.membership?.role ?? "No active membership"}</small>
          </div>
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav>
          {views.map((name, index) => (
            <button
              key={name}
              aria-current={view === name ? "page" : undefined}
              className={view === name ? "selected" : ""}
              onClick={() => go(name)}
            >
              <span>{icons[index]}</span>
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="eyebrow">● LOCAL DEMO</span>
          <p>
            Built for learning.
            <br />
            Not for production data.
          </p>
          <small>{user.email}</small>
          <button
            className="text-button"
            disabled={busy}
            onClick={() =>
              void perform(async () => {
                await api("auth/logout/", "POST", {});
                setUser(null);
                setOrg(null);
                setCart([]);
              })
            }
          >
            Sign out ↗
          </button>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <span>
            Workspace <span className="slash">/</span> {view}
          </span>
            <span className="connection">● Local workspace</span>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">{org?.name ?? "WORKSPACE"}</span>
              <h1>{view === "Overview" ? "Business, in view." : view}</h1>
              <p className="subtle">
                {view === "Overview"
                  ? "A little clarity for your everyday operations."
                  : "Live organization data · " + (org?.currency ?? "")}
              </p>
            </div>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => void perform(load, "Workspace refreshed.")}
            >
              ↻ Refresh
            </button>
          </div>
          {error && (
            <div className="alert" role="alert">
              {error}
            </div>
          )}
          {notice && (
            <div className="success" role="status">
              {notice}
            </div>
          )}
          {busy && (
            <div className="working" role="status">
              Saving or loading…
            </div>
          )}
          <fieldset className="workspace-content" disabled={busy}>
            {view === "Overview" && (
              <>
                <div className="metrics">
                  {[
                    ["Products", products.count, "In your catalog", "▦"],
                    ["Variants", stock.count, "Stock-tracked identities", "▤"],
                    [
                      "Sales recorded",
                      sales.count,
                      "Includes cancelled sales",
                      "↗",
                    ],
                  ].map(([label, count, caption, icon]) => (
                    <article className="metric" key={label}>
                      <span className="metric-icon">{icon}</span>
                      <span>{label}</span>
                      <strong>{count}</strong>
                      <small>{caption}</small>
                    </article>
                  ))}
                </div>
                <section className="welcome-banner">
                  <div>
                    <span className="eyebrow">A CONNECTED WORKFLOW</span>
                    <h2>Your next sale starts here.</h2>
                    <p>
                      Create a product, add stock, then record a sale.
                      <br />
                      We’ll keep the quantities and history in sync.
                    </p>
                    <button
                      className="primary"
                      onClick={() => go(admin ? "Products" : "New sale")}
                    >
                      {admin ? "Manage products" : "Record a sale"} →
                    </button>
                  </div>
                  <div className="flow-illustration" aria-hidden="true">
                    <span>
                      ▦<small>CATALOG</small>
                    </span>
                    <b>→</b>
                    <span>
                      ▤<small>STOCK</small>
                    </span>
                    <b>→</b>
                    <span>
                      ↗<small>SALE</small>
                    </span>
                  </div>
                </section>
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Recent sales</h2>
                      <p className="subtle">
                        The latest activity in your workspace.
                      </p>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => go("Sales history")}
                    >
                      View all →
                    </button>
                  </div>
                  {sales.results.length ? (
                    <SalesTable
                      rows={sales.results.slice(0, 5)}
                      select={(s) => {
                        go("Sales history");
                        setSelectedSale(s);
                      }}
                    />
                  ) : (
                    <Empty text="No sales yet. Add stock and record your first sale." />
                  )}
                </section>
              </>
            )}
            {view === "Products" && (
              <>
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Product catalog</h2>
                    <Badge active>{products.count} products</Badge>
                  </div>
                  {products.results.length ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Product</th>
                            <th>Variants</th>
                            <th>Availability</th>
                          </tr>
                        </thead>
                        <tbody>
                          {products.results.map((p) => (
                            <tr key={p.id}>
                              <td>
                                <strong>{p.name}</strong>
                                <small className="row-hint">
                                  {p.id.slice(0, 8)}
                                </small>
                              </td>
                              <td>{p.variant_count}</td>
                              <td>
                                <Badge active={p.is_available}>
                                  {p.is_available ? "Available" : "Inactive"}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <Empty text="Your catalog starts with a category and a product." />
                  )}
                  <Pager
                    page={products}
                    onPage={(path) => paginate(path, setProducts)}
                  />
                </section>
                {admin ? (
                  <div className="form-grid">
                    <section className="panel form-panel">
                      <h2>Add a category</h2>
                      <p className="subtle">
                        A simple way to organize your products.
                      </p>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          const form = e.currentTarget;
                          const name = new FormData(form).get("name");
                          void perform(async () => {
                            await api("categories/", "POST", { name });
                            await load();
                            form.reset();
                          }, "Category created.");
                        }}
                      >
                        <Field label="Category name">
                          <input
                            name="name"
                            required
                            maxLength={120}
                            placeholder="e.g. Everyday essentials"
                          />
                        </Field>
                        <button className="secondary">Create category</button>
                      </form>
                      <Pager
                        page={categories}
                        onPage={(path) => paginate(path, setCategories)}
                      />
                    </section>
                    <section className="panel form-panel">
                      <h2>Create a product</h2>
                      <p className="subtle">
                        Include at least one unique variant.
                      </p>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          const form = e.currentTarget;
                          const data = new FormData(form);
                          void perform(async () => {
                            await api("products/", "POST", {
                              name: data.get("name"),
                              category_id: data.get("category_id"),
                              variants,
                            });
                            await load();
                            form.reset();
                            setVariants([
                              { sku: "", price: "", size: "", color: "" },
                            ]);
                          }, "Product and variants created.");
                        }}
                      >
                        <Field label="Product name">
                          <input
                            name="name"
                            required
                            maxLength={160}
                            placeholder="e.g. Everyday shirt"
                          />
                        </Field>
                        <Field label="Category">
                          <select name="category_id" required defaultValue="">
                            <option value="" disabled>
                              Select a category
                            </option>
                            {categories.results
                              .filter((c) => c.is_active)
                              .map((c) => (
                                <option key={c.id} value={c.id}>
                                  {c.name}
                                </option>
                              ))}
                          </select>
                        </Field>
                        {variants.map((v, index) => (
                          <div className="variant-form" key={index}>
                            <div className="panel-heading">
                              <strong>Variant {index + 1}</strong>
                              {index > 0 && (
                                <button
                                  type="button"
                                  className="text-button"
                                  onClick={() =>
                                    setVariants(
                                      variants.filter((_, i) => i !== index),
                                    )
                                  }
                                >
                                  Remove
                                </button>
                              )}
                            </div>
                            <div className="two-columns">
                              {(["sku", "price", "size", "color"] as const).map(
                                (key) => (
                                  <Field
                                    key={key}
                                    label={
                                      key === "sku"
                                        ? "SKU"
                                        : key.charAt(0).toUpperCase() +
                                          key.slice(1)
                                    }
                                  >
                                    <input
                                      value={v[key]}
                                      required={
                                        key === "sku" || key === "price"
                                      }
                                      maxLength={key === "sku" ? 64 : 40}
                                      inputMode={
                                        key === "price" ? "decimal" : undefined
                                      }
                                      pattern={
                                        key === "price"
                                          ? "[0-9]{1,10}(\\.[0-9]{1,2})?"
                                          : undefined
                                      }
                                      placeholder={
                                        key === "price"
                                          ? "12.50"
                                          : key === "sku"
                                            ? "SHIRT-001"
                                            : "Optional"
                                      }
                                      onChange={(e) =>
                                        setVariants(
                                          variants.map((item, i) =>
                                            i === index
                                              ? {
                                                  ...item,
                                                  [key]: e.target.value,
                                                }
                                              : item,
                                          ),
                                        )
                                      }
                                    />
                                  </Field>
                                ),
                              )}
                            </div>
                          </div>
                        ))}
                        <div className="form-actions">
                          <button
                            type="button"
                            className="secondary"
                            disabled={variants.length >= 50}
                            onClick={() =>
                              setVariants([
                                ...variants,
                                { sku: "", price: "", size: "", color: "" },
                              ])
                            }
                          >
                            + Add variant
                          </button>
                          <button className="primary">Create product</button>
                        </div>
                      </form>
                    </section>
                  </div>
                ) : (
                  <div className="info">
                    STAFF can browse the catalog. An ADMIN manages products.
                  </div>
                )}
              </>
            )}
            {view === "Inventory" && (
              <>
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Stock on hand</h2>
                    <Badge active>{stock.count} variants</Badge>
                  </div>
                  <StockTable rows={stock.results} />
                  <Pager
                    page={stock}
                    onPage={(path) => paginate(path, setStock)}
                  />
                </section>
                {admin && (
                  <section className="panel form-panel">
                    <h2>Adjust stock</h2>
                    <p className="subtle">
                      Positive units add stock. Negative units remove it. Every
                      change is recorded.
                    </p>
                    <form
                      className="inline-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const form = e.currentTarget;
                        const data = new FormData(form);
                        void perform(async () => {
                          await api("inventory/adjustments/", "POST", {
                            variant_id: data.get("variant_id"),
                            delta: Number(data.get("delta")),
                            reason: data.get("reason"),
                          });
                          await load();
                          form.reset();
                        }, "Stock updated. Movement recorded.");
                      }}
                    >
                      <Field label="Variant (current page)">
                        <select name="variant_id" required defaultValue="">
                          <option value="" disabled>
                            Select a variant
                          </option>
                          {stock.results.map((s) => (
                            <option key={s.variant_id} value={s.variant_id}>
                              {s.sku} · {s.product_name}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Unit change">
                        <input
                          name="delta"
                          type="number"
                          min={-10000}
                          max={10000}
                          step={1}
                          required
                          placeholder="10"
                        />
                      </Field>
                      <Field label="Reason">
                        <input
                          name="reason"
                          required
                          maxLength={160}
                          placeholder="Opening stock"
                        />
                      </Field>
                      <button className="primary">Save adjustment</button>
                    </form>
                  </section>
                )}
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Movement history</h2>
                    <span className="subtle">Read-only audit trail</span>
                  </div>
                  {movements.results.length ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Variant</th>
                            <th>Change</th>
                            <th>Reason</th>
                          </tr>
                        </thead>
                        <tbody>
                          {movements.results.map((m) => (
                            <tr key={m.id}>
                              <td>{new Date(m.created_at).toLocaleString()}</td>
                              <td className="mono">
                                {stock.results.find(
                                  (s) => s.variant_id === m.variant_id,
                                )?.sku ?? m.variant_id.slice(0, 8)}
                              </td>
                              <td>
                                <Badge active={m.delta > 0}>
                                  {m.delta > 0 ? "+" : ""}
                                  {m.delta}
                                </Badge>
                              </td>
                              <td>{m.reason}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <Empty text="No movements yet. Your first adjustment will appear here." />
                  )}
                  <Pager
                    page={movements}
                    onPage={(path) => paginate(path, setMovements)}
                  />
                </section>
              </>
            )}
            {view === "New sale" && (
              <div className="sale-grid">
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Choose variants</h2>
                    <span className="subtle">Current stock page</span>
                  </div>
                  {stock.results.length ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Product / SKU</th>
                            <th>Price</th>
                            <th>Available</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {stock.results.map((s) => (
                            <tr key={s.variant_id}>
                              <td>
                                <strong>{s.product_name}</strong>
                                <small className="row-hint">{s.sku}</small>
                              </td>
                              <td>{s.price}</td>
                              <td>{s.quantity}</td>
                              <td>
                                <button
                                  className="secondary"
                                  disabled={
                                    !s.is_available ||
                                    s.quantity < 1 ||
                                    cart.some(
                                      (c) => c.variant_id === s.variant_id,
                                    )
                                  }
                                  onClick={() =>
                                    setCart([
                                      ...cart,
                                      { variant_id: s.variant_id, quantity: 1 },
                                    ])
                                  }
                                >
                                  Add
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <Empty text="Create products and add stock before making a sale." />
                  )}
                  <Pager
                    page={stock}
                    onPage={(path) => paginate(path, setStock)}
                  />
                </section>
                <section className="panel form-panel">
                  <span className="eyebrow">ORDER SUMMARY</span>
                  <h2>New sale</h2>
                  <p className="subtle">
                    Prices and availability are checked by the server at
                    confirmation.
                  </p>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      void perform(async () => {
                        const sale = await api<Sale>("sales/", "POST", {
                          items: cart,
                        });
                        setCart([]);
                        await load();
                        go("Sales history");
                        setSelectedSale(sale);
                      }, "Sale recorded. Stock updated.");
                    }}
                  >
                    {cart.map((c) => (
                      <div className="cart-line" key={c.variant_id}>
                        <Field
                          label={
                            stock.results.find(
                              (s) => s.variant_id === c.variant_id,
                            )?.sku ?? c.variant_id.slice(0, 8)
                          }
                        >
                          <input
                            type="number"
                            min={1}
                            max={10000}
                            required
                            value={c.quantity}
                            onChange={(e) =>
                              setCart(
                                cart.map((item) =>
                                  item.variant_id === c.variant_id
                                    ? {
                                        ...item,
                                        quantity: Number(e.target.value),
                                      }
                                    : item,
                                ),
                              )
                            }
                          />
                        </Field>
                        <button
                          type="button"
                          className="text-button"
                          onClick={() =>
                            setCart(
                              cart.filter(
                                (item) => item.variant_id !== c.variant_id,
                              ),
                            )
                          }
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    {!cart.length && <Empty text="Add a variant to begin." />}
                    <button className="primary full" disabled={!cart.length}>
                      Confirm sale →
                    </button>
                    <p className="auth-foot">
                      No payments or taxes. This records a local demo sale.
                    </p>
                  </form>
                </section>
              </div>
            )}
            {view === "Sales history" && (
              <>
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Sales ledger</h2>
                    <span className="subtle">Historical prices preserved</span>
                  </div>
                  {sales.results.length ? (
                    <SalesTable rows={sales.results} select={setSelectedSale} />
                  ) : (
                    <Empty text="No sales recorded yet." />
                  )}
                  <Pager
                    page={sales}
                    onPage={(path) => paginate(path, setSales)}
                  />
                </section>
                {selectedSale && (
                  <section className="panel form-panel">
                    <div className="panel-heading">
                      <div>
                        <span className="eyebrow">
                          SALE {selectedSale.id.slice(0, 8)}
                        </span>
                        <h2>
                          {selectedSale.currency} {selectedSale.total}
                        </h2>
                      </div>
                      <Badge active={selectedSale.status === "COMPLETED"}>
                        {selectedSale.status}
                      </Badge>
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>SKU snapshot</th>
                            <th>Quantity</th>
                            <th>Unit price</th>
                            <th>Subtotal</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedSale.items.map((item, i) => (
                            <tr key={i}>
                              <td>{item.sku}</td>
                              <td>{item.quantity}</td>
                              <td>{item.unit_price}</td>
                              <td>{item.subtotal}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {admin && selectedSale.status === "COMPLETED" && (
                      <form
                        className="inline-form cancel-form"
                        onSubmit={(e) => {
                          e.preventDefault();
                          const reason = new FormData(e.currentTarget).get(
                            "reason",
                          );
                          void perform(async () => {
                            setSelectedSale(
                              await api<Sale>(
                                `sales/${selectedSale.id}/cancel/`,
                                "POST",
                                { reason },
                              ),
                            );
                            await load();
                          }, "Sale cancelled. Stock restored once.");
                        }}
                      >
                        <Field label="Cancellation reason">
                          <input
                            name="reason"
                            required
                            maxLength={160}
                            placeholder="Entry error"
                          />
                        </Field>
                        <button className="secondary">
                          Cancel sale & restore stock
                        </button>
                      </form>
                    )}
                  </section>
                )}
              </>
            )}
          </fieldset>
          <footer className="content-footer">
            Stockroom · Portfolio MVP{" "}
            <span>Organization-scoped · Session authenticated</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
function StockTable({ rows }: { rows: Stock[] }) {
  return rows.length ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Product / SKU</th>
            <th>Options</th>
            <th>Unit price</th>
            <th>On hand</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.variant_id}>
              <td>
                <strong>{s.product_name}</strong>
                <small className="row-hint mono">{s.sku}</small>
              </td>
              <td>
                {[s.size, s.color].filter(Boolean).join(" / ") || "Standard"}
              </td>
              <td>{s.price}</td>
              <td className="quantity">{s.quantity}</td>
              <td>
                <Badge active={s.is_available && s.quantity > 0}>
                  {!s.is_available
                    ? "Inactive"
                    : s.quantity > 0
                      ? "In stock"
                      : "Out of stock"}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty text="No variants yet. Create a product to start tracking stock." />
  );
}
function SalesTable({
  rows,
  select,
}: {
  rows: Sale[];
  select: (sale: Sale) => void;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Sale</th>
            <th>Date</th>
            <th>Items</th>
            <th>Total</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td className="mono">#{s.id.slice(0, 8)}</td>
              <td>{new Date(s.created_at).toLocaleDateString()}</td>
              <td>{s.items.reduce((n, i) => n + i.quantity, 0)} units</td>
              <td>
                <strong>
                  {s.currency} {s.total}
                </strong>
              </td>
              <td>
                <Badge active={s.status === "COMPLETED"}>
                  {s.status === "COMPLETED" ? "Completed" : "Cancelled"}
                </Badge>
              </td>
              <td>
                <button className="text-button" onClick={() => select(s)}>
                  View →
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
