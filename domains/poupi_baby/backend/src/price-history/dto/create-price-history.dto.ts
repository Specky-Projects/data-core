import { IsNumber, IsUUID } from 'class-validator';

export class CreatePriceHistoryDto {
  @IsUUID()
  offerId: string;

  @IsNumber()
  price: number;
}