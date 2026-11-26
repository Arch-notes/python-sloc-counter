export class Greeter {
  prefix = "hi";

  greet(name: string): string {
    return this.prefix + name;
  }
}

export const helper = (x: number) => {
  return x * 2;
};
