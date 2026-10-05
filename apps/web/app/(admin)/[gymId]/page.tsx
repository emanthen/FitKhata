export default async function GymDashboardPage({
  params,
}: {
  params: Promise<{ gymId: string }>;
}) {
  const { gymId } = await params;
  return <h1 className="text-2xl font-semibold">Gym {gymId}</h1>;
}
