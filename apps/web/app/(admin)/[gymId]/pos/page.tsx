"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createProduct,
  deleteProduct,
  listMembers,
  listProducts,
  ringUpSale,
  type Member,
  type Product,
} from "@fitkhata/api-client";
import { Plus, ShoppingCart, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/lib/auth";
import { formatNpr } from "@/lib/money";

interface BasketLine {
  product: Product;
  quantity: number;
}

export default function PosPage() {
  const { claims } = useAuth();
  const canManageProducts = claims?.role === "owner" || claims?.role === "manager";
  const queryClient = useQueryClient();

  const products = useQuery({ queryKey: ["products"], queryFn: listProducts });
  const list: Product[] = Array.isArray(products.data)
    ? products.data
    : (products.data?.results ?? []);
  const activeProducts = list.filter((p) => p.is_active);

  // --- Product management (manager+) ---
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("");
  const [productError, setProductError] = useState<string | null>(null);

  async function addProduct(e: React.FormEvent) {
    e.preventDefault();
    setProductError(null);
    try {
      await createProduct({ sku, name, price_npr: price, stock_qty: Number(stock) });
      setSku("");
      setName("");
      setPrice("");
      setStock("");
      queryClient.invalidateQueries({ queryKey: ["products"] });
    } catch {
      setProductError("Couldn't add this product — check the SKU isn't already used.");
    }
  }

  async function removeProduct(id: string) {
    await deleteProduct(id);
    queryClient.invalidateQueries({ queryKey: ["products"] });
  }

  // --- Ring-up sale ---
  const [memberQuery, setMemberQuery] = useState("");
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const memberResults = useQuery({
    queryKey: ["member-search", memberQuery],
    queryFn: () => listMembers({ q: memberQuery }),
    enabled: memberQuery.length > 1 && !selectedMember,
  });
  const memberMatches: Member[] = Array.isArray(memberResults.data)
    ? memberResults.data
    : (memberResults.data?.results ?? []);

  const [basket, setBasket] = useState<BasketLine[]>([]);
  const [saleError, setSaleError] = useState<string | null>(null);
  const [ringingUp, setRingingUp] = useState(false);
  const [lastSaleTotal, setLastSaleTotal] = useState<string | null>(null);

  function addToBasket(product: Product) {
    setBasket((prev) => {
      const existing = prev.find((line) => line.product.id === product.id);
      if (existing) {
        return prev.map((line) =>
          line.product.id === product.id ? { ...line, quantity: line.quantity + 1 } : line
        );
      }
      return [...prev, { product, quantity: 1 }];
    });
  }

  function updateQuantity(productId: string, quantity: number) {
    setBasket((prev) =>
      prev
        .map((line) => (line.product.id === productId ? { ...line, quantity } : line))
        .filter((line) => line.quantity > 0)
    );
  }

  const basketTotal = basket.reduce(
    (sum, line) => sum + Number(line.product.price_npr) * line.quantity,
    0
  );

  async function submitSale() {
    if (!selectedMember || basket.length === 0) return;
    setSaleError(null);
    setRingingUp(true);
    try {
      const sale = await ringUpSale({
        member_id: selectedMember.id,
        lines: basket.map((line) => ({ product_id: line.product.id, quantity: line.quantity })),
      });
      const total = sale.lines.reduce((sum, l) => sum + Number(l.line_total_npr), 0);
      setLastSaleTotal(total.toFixed(2));
      setBasket([]);
      setSelectedMember(null);
      setMemberQuery("");
      queryClient.invalidateQueries({ queryKey: ["products"] });
    } catch {
      setSaleError("Couldn't complete this sale — check stock levels.");
    } finally {
      setRingingUp(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <ShoppingCart size={18} strokeWidth={2} className="text-primary" />
        Point of sale
      </h1>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Ring up a sale</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {lastSaleTotal && (
              <p className="rounded-md bg-primary/10 px-2.5 py-2 text-sm text-primary">
                Sale complete — {formatNpr(lastSaleTotal, { symbol: true })} invoiced.
              </p>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="member-search">Member</Label>
              {selectedMember ? (
                <div className="flex items-center justify-between rounded-md border px-2.5 py-1.5 text-sm">
                  <span>
                    {selectedMember.full_name} · {selectedMember.member_code}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs"
                    onClick={() => setSelectedMember(null)}
                  >
                    Change
                  </Button>
                </div>
              ) : (
                <>
                  <Input
                    id="member-search"
                    value={memberQuery}
                    onChange={(e) => setMemberQuery(e.target.value)}
                    placeholder="Search by name, phone, or member code"
                    className="h-8"
                  />
                  {memberMatches.length > 0 && (
                    <ul className="max-h-40 overflow-y-auto rounded-md border text-sm">
                      {memberMatches.map((m) => (
                        <li key={m.id}>
                          <button
                            type="button"
                            className="flex w-full items-center justify-between px-2.5 py-1.5 text-left hover:bg-muted"
                            onClick={() => {
                              setSelectedMember(m);
                              setMemberQuery("");
                            }}
                          >
                            <span>{m.full_name}</span>
                            <span className="text-xs text-muted-foreground">{m.member_code}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>

            <div className="space-y-1.5">
              <Label>Products</Label>
              <div className="flex flex-wrap gap-1.5">
                {activeProducts.map((p) => (
                  <Button
                    key={p.id}
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={p.stock_qty === 0}
                    onClick={() => addToBasket(p)}
                  >
                    {p.name} · {formatNpr(p.price_npr, { symbol: true })}
                  </Button>
                ))}
                {activeProducts.length === 0 && (
                  <p className="text-sm text-muted-foreground">No products set up yet.</p>
                )}
              </div>
            </div>

            {basket.length > 0 && (
              <ul className="divide-y rounded-md border">
                {basket.map((line) => (
                  <li
                    key={line.product.id}
                    className="flex items-center justify-between px-2.5 py-1.5 text-sm"
                  >
                    <span>{line.product.name}</span>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        value={line.quantity}
                        onChange={(e) => updateQuantity(line.product.id, Number(e.target.value))}
                        className="h-7 w-16"
                      />
                      <span className="w-20 text-right font-dashboard-mono">
                        {formatNpr((Number(line.product.price_npr) * line.quantity).toFixed(2))}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {saleError && <p className="text-sm text-destructive">{saleError}</p>}
            <div className="flex items-center justify-between border-t pt-3">
              <span className="text-sm font-medium">
                Total: {formatNpr(basketTotal.toFixed(2), { symbol: true })}
              </span>
              <Button
                size="sm"
                disabled={!selectedMember || basket.length === 0 || ringingUp}
                onClick={submitSale}
              >
                {ringingUp ? "..." : "Complete sale"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Products &amp; stock</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Stock</TableHead>
                  {canManageProducts && <TableHead />}
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-dashboard-mono">{p.sku}</TableCell>
                    <TableCell>{p.name}</TableCell>
                    <TableCell>{formatNpr(p.price_npr, { symbol: true })}</TableCell>
                    <TableCell className={p.stock_qty === 0 ? "text-destructive" : ""}>
                      {p.stock_qty}
                    </TableCell>
                    {canManageProducts && (
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-destructive hover:text-destructive"
                          onClick={() => removeProduct(p.id)}
                        >
                          <Trash2 size={13} strokeWidth={2} />
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
                {list.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={canManageProducts ? 5 : 4}
                      className="py-6 text-center text-sm text-muted-foreground"
                    >
                      No products yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>

            {canManageProducts && (
              <form onSubmit={addProduct} className="space-y-3 border-t pt-3">
                <div className="flex flex-wrap items-end gap-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="product-sku">SKU</Label>
                    <Input
                      id="product-sku"
                      value={sku}
                      onChange={(e) => setSku(e.target.value)}
                      className="h-8 w-28"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="product-name">Name</Label>
                    <Input
                      id="product-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="h-8 w-40"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="product-price">Price (NPR)</Label>
                    <Input
                      id="product-price"
                      type="number"
                      step="0.01"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                      className="h-8 w-28"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="product-stock">Stock</Label>
                    <Input
                      id="product-stock"
                      type="number"
                      value={stock}
                      onChange={(e) => setStock(e.target.value)}
                      className="h-8 w-24"
                      required
                    />
                  </div>
                  <Button type="submit" size="sm">
                    <Plus size={13} strokeWidth={2} data-icon="inline-start" />
                    Add product
                  </Button>
                </div>
                {productError && <p className="text-sm text-destructive">{productError}</p>}
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
